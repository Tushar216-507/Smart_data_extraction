from extractor.downloader import PageDownloader
from extractor.cleaner import HTMLCleaner
from extractor.markdown_converter import MarkdownConverter


class PagePipeline:

    def __init__(self):

        self.downloader = PageDownloader()
        self.cleaner = HTMLCleaner()
        self.markdown = MarkdownConverter()

    def process(self, url):

        page = self.downloader.download(url)

        raw_html = page["html"]

        clean_html = self.cleaner.clean(raw_html)

        markdown = self.markdown.convert(clean_html)

        return {

            "url": url,

            "status": page.get("status", 200),

            "title": page.get("title", ""),

            "raw_html": raw_html,

            "clean_html": clean_html,

            "markdown": markdown
        }