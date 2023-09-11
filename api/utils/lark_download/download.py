import datetime
import json
from typing import Tuple

import prettytable
import regex
import lark_oapi as lark

from .define import *
from io import StringIO
from urllib.parse import unquote
from prettytable import PrettyTable
from langchain.text_splitter import Document


class LarkWiki2Md(object):
    use_html_tags: bool
    client: lark.Client

    def __init__(self, app_id: str, app_secret: str, use_html_tags: bool):
        self.use_html_tags = use_html_tags
        self.client = lark.Client.builder().app_id(app_id).app_secret(app_secret).build()

    # 检查url是否正确
    def check_url(self, url: str):
        pattern = regex.compile(r"^https://pandadagames.feishu.cn/(docx|wiki)/([a-zA-Z0-9]+)")
        match = pattern.search(url)
        if match and len(match.groups()) == 2:
            return str.lower(match.group(1)), match.group(2)
        else:
            raise Exception("url format err")

    def get_old_doc_content(self, doc_token: str):
        request = lark.BaseRequest.builder().uri("/open-apis/doc/v2/meta/:doc_token").http_method(
            lark.HttpMethod.GET).paths({"doc_token": doc_token}).token_types(
            {lark.AccessTokenType.TENANT, lark.AccessTokenType.USER}).headers(
            {"Content-Type": "application/json; charset=utf-8"}).build()
        response = self.client.request(request)
        if response.code != 0:
            raise Exception("document code: {}, msg: {}".format(response.code, response.msg))

        res_dict = json.loads(response.raw.content)
        title = res_dict["data"]["title"]

        request = lark.BaseRequest.builder().uri("/open-apis/doc/v2/:doc_token/raw_content").http_method(
            lark.HttpMethod.GET).paths({"doc_token": doc_token}).token_types(
            {lark.AccessTokenType.TENANT, lark.AccessTokenType.USER}).headers(
            {"Content-Type": "application/json; charset=utf-8"}).build()
        response = self.client.request(request)
        if response.code != 0:
            raise Exception("document code: {}, msg: {}".format(response.code, response.msg))

        res_dict = json.loads(response.raw.content)
        content = res_dict["data"]["content"]

        pattern = r'^\*'
        replaced = regex.sub(pattern, '', content, flags=regex.M)

        return lark.docx.v1.Document(dict(
            document_id=doc_token,
            title=title)
        ), replaced

    # 获取文档信息
    def get_doc_content(self, doc_type: str, doc_token: str):
        request = lark.docx.v1.GetDocumentRequest.builder().document_id(doc_token).build()
        response = self.client.docx.v1.document.get(request)
        if not response.success():
            raise Exception("document code: {}, msg: {}".format(response.code, response.msg))

        document = lark.docx.v1.Document(dict(
            document_id=response.data.document.document_id,
            revision_id=response.data.document.revision_id,
            title=response.data.document.title)
        )

        blocks = []
        page_token = ""
        while True:
            request = lark.docx.v1.ListDocumentBlockRequest.builder().document_id(doc_token).page_token(
                page_token).build()
            response = self.client.docx.v1.document_block.list(request)
            if not response.success():
                raise Exception("document block code: {}, msg: {}".format(response.code, response.msg))

            blocks.extend(response.data.items)

            if not response.data.has_more:
                break
            page_token = response.data.page_token

        return document, blocks

    def _make_md_content(self, document_id: str, blocks: [lark.docx.v1.Block]) -> str:
        block_map = {}
        for block in blocks:
            block_map[block.block_id] = block

        entry_block = block_map[document_id]

        return self._parse_docx_block(block_map, entry_block, 0)

    def _parse_docx_block(self, block_map: dict[str, lark.docx.v1.Block], block: lark.docx.v1.Block,
                          level: int = 0) -> str:
        strs = StringIO()
        strs.write("\t" * level)

        if block.block_type == DocxBlockTypePage:
            strs.write(self._parse_docx_block_page(block_map, block))
        elif block.block_type == DocxBlockTypeText:
            strs.write(self._parse_docx_block_text(block_map, block.text))
        elif block.block_type == DocxBlockTypeHeading1:
            strs.write("# ")
            strs.write(self._parse_docx_block_text(block_map, block.heading1))
        elif block.block_type == DocxBlockTypeHeading2:
            strs.write("## ")
            strs.write(self._parse_docx_block_text(block_map, block.heading2))
        elif block.block_type == DocxBlockTypeHeading3:
            strs.write("### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading3))
        elif block.block_type == DocxBlockTypeHeading4:
            strs.write("#### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading4))
        elif block.block_type == DocxBlockTypeHeading5:
            strs.write("##### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading5))
        elif block.block_type == DocxBlockTypeHeading6:
            strs.write("###### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading6))
        elif block.block_type == DocxBlockTypeHeading7:
            strs.write("####### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading7))
        elif block.block_type == DocxBlockTypeHeading8:
            strs.write("######## ")
            strs.write(self._parse_docx_block_text(block_map, block.heading8))
        elif block.block_type == DocxBlockTypeHeading9:
            strs.write("######### ")
            strs.write(self._parse_docx_block_text(block_map, block.heading9))
        elif block.block_type == DocxBlockTypeBullet:
            strs.write(self._parse_docx_block_bullet(block_map, block, level))
        elif block.block_type == DocxBlockTypeOrdered:
            strs.write(self._parse_docx_block_ordered(block_map, block, level))
        elif block.block_type == DocxBlockTypeCode:
            strs.write("```" + DocxCodeLang2MdStr[block.code.style.language] + "\n")
            strs.write(str.strip(self._parse_docx_block_text(block_map, block.code)))
            strs.write("\n```\n")
        elif block.block_type == DocxBlockTypeQuote:
            strs.write("> ")
            strs.write(self._parse_docx_block_text(block_map, block.quote))
        elif block.block_type == DocxBlockTypeEquation:
            strs.write("$$\n")
            strs.write(self._parse_docx_block_text(block_map, block.equation))
            strs.write("\n$$\n")
        elif block.block_type == DocxBlockTypeTodo:
            if block.todo.style.done:
                strs.write("- [x] ")
            else:
                strs.write("- [ ] ")
            strs.write(self._parse_docx_block_text(block_map, block.todo))
        elif block.block_type == DocxBlockTypeDivider:
            strs.write("---\n")
        elif block.block_type == DocxBlockTypeImage:
            strs.write(self._parse_docx_block_image(block_map, block.image))
        elif block.block_type == DocxBlockTypeTableCell:
            strs.write(self._parse_docx_block_table_cell(block_map, block))
        elif block.block_type == DocxBlockTypeTable:
            strs.write(self._parse_docx_block_table(block_map, block.table))
        elif block.block_type == DocxBlockTypeQuoteContainer:
            strs.write(self._parse_docx_block_quote_container(block_map, block))
        elif block.block_type == DocxBlockTypeCallout:
            strs.write(self._parse_docx_block_quote_container(block_map, block))

        return strs.getvalue()

    def _parse_docx_block_page(self, block_map: dict[str, lark.docx.v1.Block], block: lark.docx.v1.Block) -> str:
        strs = StringIO()
        strs.write("# ")
        strs.write(self._parse_docx_block_text(block_map, block.page))
        strs.write("\n")

        if block.children is not None:
            for child in block.children:
                child_block = block_map[child]
                strs.write(self._parse_docx_block(block_map, child_block, 0))
                strs.write("\n")

        return strs.getvalue()

    def _parse_docx_block_text(self, block_map: dict[str, lark.docx.v1.Block], text: lark.docx.v1.Text) -> str:
        strs = StringIO()
        num_elem = len(text.elements)

        if text.elements is not None:
            for e in text.elements:
                inline = num_elem > 1
                strs.write(self._parse_docx_block_text_element(block_map, e, inline))

        strs.write("\n")
        return strs.getvalue()

    def _parse_docx_block_text_element(self, block_map: dict[str, lark.docx.v1.Block],
                                       element: lark.docx.v1.TextElement,
                                       inline: bool = False) -> str:
        strs = StringIO()
        if element.text_run is not None:
            strs.write(self._parse_docx_block_text_element_text_run(block_map, element.text_run))

        if element.mention_user is not None:
            strs.write(element.mention_user.user_id)

        if element.mention_doc is not None:
            strs.write("[{}({})]".format(element.mention_doc.title, unquote(element.mention_doc.url)))

        if element.equation is not None:
            symbol = "$$"
            if inline:
                symbol = "$"
            strs.write(symbol + element.equation.content.removeprefix("\n") + symbol)

        return strs.getvalue()

    def _parse_docx_block_text_element_text_run(self, block_map: dict[str, lark.docx.v1.Block],
                                                text_run: lark.docx.v1.TextRun) -> str:
        strs = StringIO()
        post_write = ""
        style = text_run.text_element_style

        if style is not None:
            if style.bold:
                if self.use_html_tags:
                    strs.write("<strong>")
                    post_write = "</strong>"
                else:
                    strs.write("**")
                    post_write = "**"

            elif style.italic:
                if self.use_html_tags:
                    strs.write("<em>")
                    post_write = "</em>"
                else:
                    strs.write("_")
                    post_write = "_"

            elif style.strikethrough:
                if self.use_html_tags:
                    strs.write("<del>")
                    post_write = "</del>"
                else:
                    strs.write("~~")
                    post_write = "~~"

            elif style.underline:
                strs.write("<u>")
                post_write = "</u>"

            elif style.inline_code:
                strs.write("`")
                post_write = "`"

            elif style.link:
                strs.write("[")
                post_write = f"]({unquote(style.link.url)})"

        strs.write(text_run.content)
        strs.write(post_write)

        return strs.getvalue()

    def _parse_docx_block_bullet(self, block_map: dict[str, lark.docx.v1.Block], block: lark.docx.v1.Block,
                                 level: int = 0) -> str:
        strs = StringIO()
        strs.write("- ")
        strs.write(self._parse_docx_block_text(block_map, block.bullet))

        if block.children is not None:
            for child in block.children:
                child_block = block_map[child]
                strs.write(self._parse_docx_block(block_map, child_block, level + 1))

        return strs.getvalue()

    def _parse_docx_block_ordered(self, block_map: dict[str, lark.docx.v1.Block], block: lark.docx.v1.Block,
                                  level: int = 0) -> str:
        strs = StringIO()

        parent = block_map[block.parent_id]
        order = 1

        if parent.children is not None:
            for idx, child in enumerate(parent.children):
                if child == block.block_id:
                    for i in range(idx, -1, -1):
                        if block_map[parent.children[i]].block_type == DocxBlockTypeOrdered:
                            order += 1
                        else:
                            break
                    break

        strs.write("{}. ".format(order))
        strs.write(self._parse_docx_block_text(block_map, block.ordered))

        if block.children is not None:
            for child in block.children:
                child_block = block_map[child]
                strs.write(self._parse_docx_block(block_map, child_block, level + 1))

        return strs.getvalue()

    def _parse_docx_block_image(self, block_map: dict[str, lark.docx.v1.Block], image: lark.docx.v1.Image) -> str:
        strs = StringIO()
        strs.write("![](")
        strs.write(unquote(image.token))
        strs.write(")")
        return strs.getvalue()

    def _parse_docx_block_table_cell(self, block_map: dict[str, lark.docx.v1.Block], block: lark.docx.v1.Block) -> str:
        strs = StringIO()
        if block.children is not None:
            for child in block.children:
                child_block = block_map[child]
                strs.write(self._parse_docx_block(block_map, child_block, 0))

        return strs.getvalue()

    # 生成md表格样式
    def _render_markdown_table(self, data: [[str]]) -> str:
        table = PrettyTable()
        table.header = data[0]

        for row in data[1:]:
            table.add_row(row)

        table.hrules = prettytable.FRAME
        table.vrules = prettytable.ALL
        table.junction_char = "|"
        table.padding_width = 0

        return table.get_string()

    def _parse_docx_block_table(self, block_map: dict[str, lark.docx.v1.Block], table: lark.docx.v1.Table) -> str:
        rows = []

        if table.cells is not None:
            for idx, blockId in enumerate(table.cells):
                block = block_map[blockId]
                cell_content = self._parse_docx_block(block_map, block, 0)
                cell_content = cell_content.replace("\n", "")
                row_index = idx // table.property.column_size

                if len(rows) <= row_index + 1:
                    rows.append([])

                rows[row_index].append(cell_content)

        strs = StringIO()
        if len(rows) > 0:
            strs.write(self._render_markdown_table(rows))
            strs.write("\n")

        return strs.getvalue()

    def _parse_docx_block_quote_container(self, block_map: dict[str, lark.docx.v1.Block],
                                          block: lark.docx.v1.Block) -> str:
        strs = StringIO()

        if block.children is not None:
            for child in block.children:
                child_block = block_map[child]
                strs.write("> ")
                strs.write(self._parse_docx_block(block_map, child_block, 0))

        return strs.getvalue()

    def download(self, url: str) -> Tuple[str, Document]:
        doc_type, doc_token = self.check_url(url)
        print(doc_token)
        # 如果是wiki类型，先获取node_token
        if doc_type == "wiki":
            request = lark.wiki.v2.GetNodeSpaceRequest.builder().token(doc_token).build()
            response = self.client.wiki.v2.space.get_node(request)
            if not response.success():
                raise Exception("node space code: {}, msg: {}".format(response.code, response.msg))
            doc_type = response.data.node.obj_type
            doc_token = response.data.node.obj_token

        if doc_type == "doc":
            document, content = self.get_old_doc_content(doc_token)
        elif doc_type == "docx":
            document, document_block = self.get_doc_content(doc_type, doc_token)
            content = self._make_md_content(doc_token, document_block)
        else:
            raise Exception("doc type err")

        return document.title, Document(page_content=content,
                                        metadata={"url": url, "title": document.title,
                                                  "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                  "type": doc_type})