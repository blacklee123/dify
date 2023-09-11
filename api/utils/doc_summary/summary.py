import langchain.llms.base
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain import PromptTemplate


class DocSummary(object):
    llm: langchain.llms.BaseLLM

    def __init__(self, llm: langchain.llms.BaseLLM):
        self.llm = llm

    @staticmethod
    def calculate_token(text: str) -> int:
        return len(text) // 4

    @staticmethod
    def token2length(token: int) -> int:
        return token * 4

    def part_summary(self, text, max_token: int, summary_len: int) -> str:
        if len(text) == 0:
            return ""

        prompt = PromptTemplate.from_template("""
        你是一个出色文档阅读者，可以很好地归纳一段内容的核心内容。
        下面是一段文档的内容：
        ```
        {{text}}
        ```
        请你以对这段内容进行归纳摘要，摘要字符数必须限制在{{summary_len}}个词以内。
        """, template_format="jinja2").format(text=text, summary_len=summary_len)

        result = self.llm(prompt)
        if len(result) > self.token2length(max_token) // 2:
            raise Exception("summary length more than half of max_token")
        return result

    def collect_summary(self, text: [str], max_token: int, summary_len: int) -> str:
        if len(text) == 0:
            return ""

        template = PromptTemplate.from_template("""
        你是一个出色文档阅读者，可以很好的将多段内容摘要进行再总结归纳。
        下面是多段内容的摘要：
        格式：
        [SummaryA]
        [SummaryB]
        [SummaryC]
        内容：
        {{text}}
        请你以对这些内容进行归纳摘要，摘要字符数必须限制在{{summary_len}}个词以内。
        """, template_format="jinja2")

        summarys = []
        texts = ""
        for t in text:
            ct = "[{}]\n".format(t)
            if len(ct) + len(texts) > self.token2length(max_token):
                result = self.llm(template.format(text=texts, summary_len=summary_len))
                if len(result) > self.token2length(max_token) // 2:
                    raise Exception("summary length more than half of max_token")
                summarys.append(result)
            texts += ct

        if len(texts) > 0:
            summarys.append(self.llm(template.format(text=texts, summary_len=summary_len)))

        if len(summarys) > 1:
            return self.collect_summary(summarys, max_token, summary_len)

        return summarys[0]

    def summary(self, text: str, max_token: int, summary_len: int) -> str:
        # 检查text有多长，选择合适的分词方式,不能大于max_token
        # 1. 如果text长度小于max_token，直接返回
        max_length = self.token2length(max_token)
        texts = []
        if len(text) < max_length:
            texts.append(text)
        else:
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=max_length,
                chunk_overlap=max_length // 10,
                length_function=len,
            )

            texts = text_splitter.split_text(text)

        # 使用llm进行摘要
        part_summary = []
        for text in texts:
            part_summary.append(self.part_summary(text, max_token, summary_len))

        # 如果只有一段，直接返回
        if len(part_summary) == 1:
            return part_summary[0]

        # 拼接摘要
        return self.collect_summary(part_summary, max_token, summary_len)