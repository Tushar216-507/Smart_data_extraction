import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/137.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9"
}


class PageDownloader:

    def __init__(
        self,
        timeout=30,
        verify_ssl=True
    ):

        self.timeout = timeout

        self.session = requests.Session()

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=1,
            status_forcelist=[
                429,
                500,
                502,
                503,
                504
            ],
            allowed_methods=[
                "GET",
                "HEAD"
            ]
        )

        adapter = HTTPAdapter(
            max_retries=retry
        )

        self.session.mount(
            "http://",
            adapter
        )

        self.session.mount(
            "https://",
            adapter
        )

        self.session.headers.update(
            DEFAULT_HEADERS
        )

        self.verify_ssl = verify_ssl

    def download(self, url):

        response = self.session.get(
            url,
            timeout=self.timeout,
            allow_redirects=True,
            verify=self.verify_ssl
        )

        response.raise_for_status()

        response.encoding = (
            response.apparent_encoding
        )

        return {

            "url": response.url,

            "status": response.status_code,

            "content_type":
                response.headers.get(
                    "Content-Type",
                    ""
                ),

            "html": response.text
        }