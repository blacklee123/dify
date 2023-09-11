from core.login.login import login_required
from flask_restful import Resource
from flask import request, current_app

from controllers.console import api
from controllers.console.setup import setup_required
from controllers.console.wraps import account_initialization_required

from utils.lark_download.download import LarkWiki2Md
from utils.doc_splitter.splitter import MD2HtmlSplitter


class LarkPreviewApi(Resource):
    @setup_required
    @login_required
    @account_initialization_required
    def get(self):
        link = request.args.get("link")
        try:
            exector = LarkWiki2Md(current_app.config.get('LARK_CLIENT_ID'), current_app.config.get('LARK_CLIENT_SECRET'), False)
            title, content = exector.download(link)
        except Exception as e:
            return {'content': '', 'title': ''}, 400

        return {'content': content.page_content, 'title': title}


api.add_resource(LarkPreviewApi, '/lark/preview')
