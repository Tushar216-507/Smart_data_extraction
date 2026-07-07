from extractor.downloader import PageDownloader

d = PageDownloader()

page = d.download(
    "https://www.lmu.de/en/study/all-degrees-and-programs/"
)

print(page["status"])
print(page["url"])
print(len(page["html"]))