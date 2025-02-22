# -*- coding:utf-8 -*-
import flask_restful
from flask import request, current_app
from flask_login import current_user

from controllers.console.apikey import api_key_list, api_key_fields
from libs.login import login_required
from flask_restful import Resource, reqparse, marshal, marshal_with
from werkzeug.exceptions import NotFound, Forbidden
import services
from controllers.console import api
from controllers.console.app.error import ProviderNotInitializeError
from controllers.console.datasets.error import DatasetNameDuplicateError
from controllers.console.setup import setup_required
from controllers.console.wraps import account_initialization_required
from core.indexing_runner import IndexingRunner
from core.model_providers.error import LLMBadRequestError, ProviderTokenNotInitError
from core.model_providers.models.entity.model_params import ModelType
from fields.app_fields import related_app_list
from fields.dataset_fields import dataset_detail_fields, dataset_query_detail_fields
from fields.document_fields import document_status_fields
from extensions.ext_database import db
from models.dataset import DocumentSegment, Document
from models.model import UploadFile, ApiToken
from services.dataset_service import DatasetService, DocumentService
from services.provider_service import ProviderService
from utils.lark_download.download import LarkWiki2Md


def _validate_name(name):
    if not name or len(name) < 1 or len(name) > 40:
        raise ValueError('Name must be between 1 to 40 characters.')
    return name


def _validate_description_length(description):
    if len(description) > 400:
        raise ValueError('Description cannot exceed 400 characters.')
    return description


class DatasetListApi(Resource):

    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)
        ids = request.args.getlist('ids')
        provider = request.args.get('provider', default="vendor")
        if ids:
            datasets, total = DatasetService.get_datasets_by_ids(ids, current_user.current_tenant_id)
        else:
            datasets, total = DatasetService.get_datasets(page, limit, provider,
                                                          current_user.current_tenant_id, current_user)

        # check embedding setting
        provider_service = ProviderService()
        valid_model_list = provider_service.get_valid_model_list(current_user.current_tenant_id,
                                                                 ModelType.EMBEDDINGS.value)
        # if len(valid_model_list) == 0:
        #     raise ProviderNotInitializeError(
        #         f"No Embedding Model available. Please configure a valid provider "
        #         f"in the Settings -> Model Provider.")
        model_names = []
        for valid_model in valid_model_list:
            model_names.append(f"{valid_model['model_name']}:{valid_model['model_provider']['provider_name']}")
        data = marshal(datasets, dataset_detail_fields)
        for item in data:
            if item['indexing_technique'] == 'high_quality':
                item_model = f"{item['embedding_model']}:{item['embedding_model_provider']}"
                if item_model in model_names:
                    item['embedding_available'] = True
                else:
                    item['embedding_available'] = False
            else:
                item['embedding_available'] = True
        response = {
            'data': data,
            'has_more': len(datasets) == limit,
            'limit': limit,
            'total': total,
            'page': page
        }
        return response, 200

    @setup_required
    @login_required
    @account_initialization_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('name', nullable=False, required=True,
                            help='type is required. Name must be between 1 to 40 characters.',
                            type=_validate_name)
        parser.add_argument('indexing_technique', type=str, location='json',
                            choices=('high_quality', 'economy'),
                            help='Invalid indexing technique.')
        args = parser.parse_args()

        # The role of the current user in the ta table must be admin or owner
        if current_user.current_tenant.current_role not in ['admin', 'owner']:
            raise Forbidden()

        try:
            dataset = DatasetService.create_empty_dataset(
                tenant_id=current_user.current_tenant_id,
                name=args['name'],
                indexing_technique=args['indexing_technique'],
                account=current_user
            )
        except services.errors.dataset.DatasetNameDuplicateError:
            raise DatasetNameDuplicateError()

        return marshal(dataset, dataset_detail_fields), 201


class DatasetApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self, dataset_id):
        dataset_id_str = str(dataset_id)
        dataset = DatasetService.get_dataset(dataset_id_str)
        if dataset is None:
            raise NotFound("Dataset not found.")
        try:
            DatasetService.check_dataset_permission(
                dataset, current_user)
        except services.errors.account.NoPermissionError as e:
            raise Forbidden(str(e))
        data = marshal(dataset, dataset_detail_fields)
        # check embedding setting
        provider_service = ProviderService()
        # get valid model list
        valid_model_list = provider_service.get_valid_model_list(current_user.current_tenant_id,
                                                                 ModelType.EMBEDDINGS.value)
        model_names = []
        for valid_model in valid_model_list:
            model_names.append(f"{valid_model['model_name']}:{valid_model['model_provider']['provider_name']}")
        if data['indexing_technique'] == 'high_quality':
            item_model = f"{data['embedding_model']}:{data['embedding_model_provider']}"
            if item_model in model_names:
                data['embedding_available'] = True
            else:
                data['embedding_available'] = False
        else:
            data['embedding_available'] = True
        return data, 200

    @setup_required
    @login_required
    @account_initialization_required
    def patch(self, dataset_id):
        dataset_id_str = str(dataset_id)
        dataset = DatasetService.get_dataset(dataset_id_str)
        if dataset is None:
            raise NotFound("Dataset not found.")
        # check user's model setting
        DatasetService.check_dataset_model_setting(dataset)

        parser = reqparse.RequestParser()
        parser.add_argument('name', nullable=False,
                            help='type is required. Name must be between 1 to 40 characters.',
                            type=_validate_name)
        parser.add_argument('description',
                            location='json', store_missing=False,
                            type=_validate_description_length)
        parser.add_argument('indexing_technique', type=str, location='json',
                            choices=('high_quality', 'economy'),
                            help='Invalid indexing technique.')
        parser.add_argument('permission', type=str, location='json', choices=(
            'only_me', 'all_team_members'), help='Invalid permission.')
        args = parser.parse_args()

        # The role of the current user in the ta table must be admin or owner
        if current_user.current_tenant.current_role not in ['admin', 'owner']:
            raise Forbidden()

        dataset = DatasetService.update_dataset(
            dataset_id_str, args, current_user)

        if dataset is None:
            raise NotFound("Dataset not found.")

        return marshal(dataset, dataset_detail_fields), 200

    @setup_required
    @login_required
    @account_initialization_required
    def delete(self, dataset_id):
        dataset_id_str = str(dataset_id)

        # The role of the current user in the ta table must be admin or owner
        if current_user.current_tenant.current_role not in ['admin', 'owner']:
            raise Forbidden()

        if DatasetService.delete_dataset(dataset_id_str, current_user):
            return {'result': 'success'}, 204
        else:
            raise NotFound("Dataset not found.")


class DatasetQueryApi(Resource):

    @setup_required
    @login_required
    @account_initialization_required
    def get(self, dataset_id):
        dataset_id_str = str(dataset_id)
        dataset = DatasetService.get_dataset(dataset_id_str)
        if dataset is None:
            raise NotFound("Dataset not found.")

        try:
            DatasetService.check_dataset_permission(dataset, current_user)
        except services.errors.account.NoPermissionError as e:
            raise Forbidden(str(e))

        page = request.args.get('page', default=1, type=int)
        limit = request.args.get('limit', default=20, type=int)

        dataset_queries, total = DatasetService.get_dataset_queries(
            dataset_id=dataset.id,
            page=page,
            per_page=limit
        )

        response = {
            'data': marshal(dataset_queries, dataset_query_detail_fields),
            'has_more': len(dataset_queries) == limit,
            'limit': limit,
            'total': total,
            'page': page
        }
        return response, 200


class DatasetIndexingEstimateApi(Resource):

    @setup_required
    @login_required
    @account_initialization_required
    def post(self):
        parser = reqparse.RequestParser()
        parser.add_argument('info_list', type=dict, required=True, nullable=True, location='json')
        parser.add_argument('process_rule', type=dict, required=True, nullable=True, location='json')
        parser.add_argument('indexing_technique', type=str, required=True, nullable=True, location='json')
        parser.add_argument('doc_form', type=str, default='text_model', required=False, nullable=False, location='json')
        parser.add_argument('dataset_id', type=str, required=False, nullable=False, location='json')
        parser.add_argument('doc_language', type=str, default='English', required=False, nullable=False,
                            location='json')
        args = parser.parse_args()
        # validate args
        DocumentService.estimate_args_validate(args)
        if args['info_list']['data_source_type'] == 'upload_file':
            file_ids = args['info_list']['file_info_list']['file_ids']
            file_details = db.session.query(UploadFile).filter(
                UploadFile.tenant_id == current_user.current_tenant_id,
                UploadFile.id.in_(file_ids)
            ).all()

            if file_details is None:
                raise NotFound("File not found.")

            indexing_runner = IndexingRunner()

            try:
                response = indexing_runner.file_indexing_estimate(current_user.current_tenant_id, file_details,
                                                                  args['process_rule'], args['doc_form'],
                                                                  args['doc_language'], args['dataset_id'],
                                                                  args['indexing_technique'])
            except LLMBadRequestError:
                raise ProviderNotInitializeError(
                    f"No Embedding Model available. Please configure a valid provider "
                    f"in the Settings -> Model Provider.")
            except ProviderTokenNotInitError as ex:
                raise ProviderNotInitializeError(ex.description)
        elif args['info_list']['data_source_type'] == 'lark_import':
            file_ids = args['info_list']['file_info_list']['file_ids']
            exector = LarkWiki2Md(current_app.config.get('LARK_CLIENT_ID'), current_app.config.get('LARK_CLIENT_SECRET'), False)
            # spliter = MD2HtmlSplitter(split_chunk_size=150, single_block_overlap=20, mul_block_overlap_threshold=20,
            #                               mul_block_overlap_ratio=2)
            _, file_details = exector.download(file_ids[0])

            indexing_runner = IndexingRunner()

            try:
                response = indexing_runner.lark_indexing_estimate(current_user.current_tenant_id, [file_details],
                                                                  args['process_rule'], args['doc_form'],
                                                                  args['doc_language'], args['dataset_id'],
                                                                  args['indexing_technique'])
            except LLMBadRequestError:
                raise ProviderNotInitializeError(
                    f"No Embedding Model available. Please configure a valid provider "
                    f"in the Settings -> Model Provider.")
            except ProviderTokenNotInitError as ex:
                raise ProviderNotInitializeError(ex.description)
        elif args['info_list']['data_source_type'] == 'notion_import':

            indexing_runner = IndexingRunner()

            try:
                response = indexing_runner.notion_indexing_estimate(current_user.current_tenant_id,
                                                                    args['info_list']['notion_info_list'],
                                                                    args['process_rule'], args['doc_form'],
                                                                    args['doc_language'], args['dataset_id'],
                                                                    args['indexing_technique'])
            except LLMBadRequestError:
                raise ProviderNotInitializeError(
                    f"No Embedding Model available. Please configure a valid provider "
                    f"in the Settings -> Model Provider.")
            except ProviderTokenNotInitError as ex:
                raise ProviderNotInitializeError(ex.description)
        else:
            raise ValueError('Data source type not support')
        return response, 200


class DatasetRelatedAppListApi(Resource):

    @setup_required
    @login_required
    @account_initialization_required
    @marshal_with(related_app_list)
    def get(self, dataset_id):
        dataset_id_str = str(dataset_id)
        dataset = DatasetService.get_dataset(dataset_id_str)
        if dataset is None:
            raise NotFound("Dataset not found.")

        try:
            DatasetService.check_dataset_permission(dataset, current_user)
        except services.errors.account.NoPermissionError as e:
            raise Forbidden(str(e))

        app_dataset_joins = DatasetService.get_related_apps(dataset.id)

        related_apps = []
        for app_dataset_join in app_dataset_joins:
            app_model = app_dataset_join.app
            if app_model:
                related_apps.append(app_model)

        return {
            'data': related_apps,
            'total': len(related_apps)
        }, 200


class DatasetIndexingStatusApi(Resource):

    @setup_required
    @login_required
    @account_initialization_required
    def get(self, dataset_id):
        dataset_id = str(dataset_id)
        documents = db.session.query(Document).filter(
            Document.dataset_id == dataset_id,
            Document.tenant_id == current_user.current_tenant_id
        ).all()
        documents_status = []
        for document in documents:
            completed_segments = DocumentSegment.query.filter(DocumentSegment.completed_at.isnot(None),
                                                              DocumentSegment.document_id == str(document.id),
                                                              DocumentSegment.status != 're_segment').count()
            total_segments = DocumentSegment.query.filter(DocumentSegment.document_id == str(document.id),
                                                          DocumentSegment.status != 're_segment').count()
            document.completed_segments = completed_segments
            document.total_segments = total_segments
            documents_status.append(marshal(document, document_status_fields))
        data = {
            'data': documents_status
        }
        return data


class DatasetApiKeyApi(Resource):
    max_keys = 10
    token_prefix = 'dataset-'
    resource_type = 'dataset'

    @setup_required
    @login_required
    @account_initialization_required
    @marshal_with(api_key_list)
    def get(self):
        keys = db.session.query(ApiToken). \
            filter(ApiToken.type == self.resource_type, ApiToken.tenant_id == current_user.current_tenant_id). \
            all()
        return {"items": keys}

    @setup_required
    @login_required
    @account_initialization_required
    @marshal_with(api_key_fields)
    def post(self):
        # The role of the current user in the ta table must be admin or owner
        if current_user.current_tenant.current_role not in ['admin', 'owner']:
            raise Forbidden()

        current_key_count = db.session.query(ApiToken). \
            filter(ApiToken.type == self.resource_type, ApiToken.tenant_id == current_user.current_tenant_id). \
            count()

        if current_key_count >= self.max_keys:
            flask_restful.abort(
                400,
                message=f"Cannot create more than {self.max_keys} API keys for this resource type.",
                code='max_keys_exceeded'
            )

        key = ApiToken.generate_api_key(self.token_prefix, 24)
        api_token = ApiToken()
        api_token.tenant_id = current_user.current_tenant_id
        api_token.token = key
        api_token.type = self.resource_type
        db.session.add(api_token)
        db.session.commit()
        return api_token, 200


class DatasetApiDeleteApi(Resource):
    resource_type = 'dataset'
    @setup_required
    @login_required
    @account_initialization_required
    def delete(self, api_key_id):
        api_key_id = str(api_key_id)

        # The role of the current user in the ta table must be admin or owner
        if current_user.current_tenant.current_role not in ['admin', 'owner']:
            raise Forbidden()

        key = db.session.query(ApiToken). \
            filter(ApiToken.tenant_id == current_user.current_tenant_id, ApiToken.type == self.resource_type,
                   ApiToken.id == api_key_id). \
            first()

        if key is None:
            flask_restful.abort(404, message='API key not found')

        db.session.query(ApiToken).filter(ApiToken.id == api_key_id).delete()
        db.session.commit()

        return {'result': 'success'}, 204


class DatasetApiBaseUrlApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        return {
            'api_base_url': (current_app.config['SERVICE_API_URL'] if current_app.config['SERVICE_API_URL']
                             else request.host_url.rstrip('/')) + '/v1'
        }


api.add_resource(DatasetListApi, '/datasets')
api.add_resource(DatasetApi, '/datasets/<uuid:dataset_id>')
api.add_resource(DatasetQueryApi, '/datasets/<uuid:dataset_id>/queries')
api.add_resource(DatasetIndexingEstimateApi, '/datasets/indexing-estimate')
api.add_resource(DatasetRelatedAppListApi, '/datasets/<uuid:dataset_id>/related-apps')
api.add_resource(DatasetIndexingStatusApi, '/datasets/<uuid:dataset_id>/indexing-status')
api.add_resource(DatasetApiKeyApi, '/datasets/api-keys')
api.add_resource(DatasetApiDeleteApi, '/datasets/api-keys/<uuid:api_key_id>')
api.add_resource(DatasetApiBaseUrlApi, '/datasets/api-base-info')
