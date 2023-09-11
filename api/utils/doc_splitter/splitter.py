import os
import uuid
import mammoth
import mistune

from lxml import html
from pdf2docx import Converter
from langchain.text_splitter import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter, Document, TextSplitter,Iterable,List


class MD2HtmlSplitter(TextSplitter):
    single_block_overlap: int  # 块大小
    split_chunk_size: int  # 重叠块大小
    mul_block_overlap_threshold: int  # 往前包容大小
    mul_block_overlap_ratio: int  # 包容比例

    text_splitter: RecursiveCharacterTextSplitter
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[
        ("#", "Header 1"),
        ("##", "Header 2"),
        # ("###", "Header 3"),
    ])

    def __init__(self, single_block_overlap: int = None, split_chunk_size: int = None,
                 mul_block_overlap_threshold: int = None,
                 mul_block_overlap_ratio: int = None, **kwargs):
        super().__init__(**kwargs)
        self.split_chunk_size = split_chunk_size if split_chunk_size else 150
        self.single_block_overlap = single_block_overlap if single_block_overlap else 20
        self.mul_block_overlap_threshold = mul_block_overlap_threshold if mul_block_overlap_threshold else 20
        self.mul_block_overlap_ratio = mul_block_overlap_ratio if mul_block_overlap_ratio else 2

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.split_chunk_size,
            chunk_overlap=self.single_block_overlap,
            length_function=len,
        )

    def split_text(self, text: str) -> [str]:
        cs = []
        for c in self.md2block("", text):
            cs.append(c.page_content)
        return cs

    def pdf2block(self, path: str, content: str) -> list[Document]:
        if len(path) > 0:
            new_path = "path-{}.docx".format(str(uuid.uuid1()))
            print(new_path)

            cv = Converter(path)
            cv.convert(new_path)
            cv.close()
        else:
            path = str(uuid.uuid1())

            try:
                with open(path, 'w', encoding='utf-8') as wf:
                    wf.write(content)

                new_path = str(uuid.uuid1())
                cv = Converter(path)
                cv.convert(new_path)
                cv.close()
            finally:
                os.remove(path)

        try:
            with open(new_path, "rb") as f:
                result = mammoth.convert_to_html(f)
                result_html = result.value
        finally:
            os.remove(new_path)

        return list(map(lambda x: Document(metadata={}, page_content=x), self.block_aggregate(
            self.node_iterate(html.fromstring(result_html)))))

    def md2block(self, path: str, content: str) -> list[Document]:
        if len(path) > 0:
            with open(path, encoding='utf-8') as f:
                content = f.read()

        doc = [Document(page_content=content, metadata={})]
        doc_real = []
        for d in doc:
            meta = d.metadata
            for sub_doc in self.block_aggregate(self.node_iterate(html.fromstring(mistune.html(d.page_content)))):
                doc_real.append(Document(metadata=meta, page_content=sub_doc))
        return doc_real

        # 直接对所有的内容进行分割
        # return self.block_aggregate(self.node_iterate(html.fromstring(mistune.html(content))))

    # 存在很多标题小块，粗略合并到下方的详细内容中，补充语义
    def block_aggregate(self, block: list[str]) -> list[str]:
        j = {}
        for i in range(len(block)):
            if i > 0:
                if len(block[i - 1]) < self.mul_block_overlap_threshold and len(block[i]) / len(
                        block[i - 1]) > self.mul_block_overlap_ratio:
                    block[i] = '{} {}'.format(block[i - 1], block[i])
                    j[i - 1] = 1

        # 剔除被合并的短文本
        new_block = []
        for i in range(len(block)):
            if i in j:
                continue
            new_block.append(block[i])

        return new_block

    def node_iterate(self, node) -> list[str]:
        if node is not None:
            all_n = []

            # 取本节点的文本
            text = node.text
            if text and len(text.strip()) > 0:
                all_n.extend(self.text_splitter.split_text(text.strip()))

            child_list = node.getchildren()
            if child_list:
                tmp_n, tmp_length = [], 0

                # 深搜子节点
                for n in child_list:
                    ns = self.node_iterate(n)
                    # 如果大于一个节点，说明子节点聚合后存在超过规定大小的块,那么直接合并到all中
                    if len(ns) > 1:
                        if tmp_length > 0:
                            all_n.append(' '.join(tmp_n))
                            tmp_n, tmp_length = [], 0
                        all_n.extend(ns)
                    else:
                        # 如果之前已经聚合超过规定大小的块,则先并入到all中
                        if tmp_length > self.split_chunk_size:
                            all_n.append(' '.join(tmp_n))
                            tmp_n, tmp_length = [], 0

                        # 将单独的块放入tem中，等待合并
                        tmp_n.extend(ns)
                        if len(ns) > 0:
                            tmp_length += len(ns[0])

                # 尾块合并
                if tmp_length > 0:
                    all_n.append(' '.join(tmp_n))

            return all_n