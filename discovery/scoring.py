from urllib.parse import urlparse

from discovery.models import CandidateURL


class URLScorer:
    """
    Scores candidate URLs based on multiple signals.

    The score is later used to rank and filter candidate
    program pages.
    """

    POSITIVE_PATH_KEYWORDS = {
        "program": 20,
        "programs": 20,
        "course": 20,
        "courses": 20,
        "degree": 25,
        "degrees": 25,
        "study": 20,
        "studies": 20,
        "bachelor": 40,
        "bachelors": 40,
        "master": 40,
        "masters": 40,
        "undergraduate": 35,
        "postgraduate": 35,
        "graduate": 25,
        "catalog": 25,
        "catalogue": 25,
        "curriculum": 25,
        "major": 30,
        "minor": 25,
        "academics": 15,
        "academic": 15,
    }

    NEGATIVE_PATH_KEYWORDS = {
        "news": -100,
        "event": -100,
        "events": -100,
        "blog": -80,
        "press": -80,
        "alumni": -80,
        "career": -60,
        "jobs": -60,
        "staff": -50,
        "people": -50,
        "contact": -50,
        "privacy": -100,
        "cookie": -100,
        "login": -100,
    }

    SOURCE_BONUS = {
        "catalog": 40,
        "navigation": 25,
        "search": 20,
        "sitemap": 15,
        "crawler": 0,
    }

    def score(self, candidate: CandidateURL) -> CandidateURL:

        score = 0

        path = urlparse(candidate.url).path.lower()

        for keyword, value in self.POSITIVE_PATH_KEYWORDS.items():
            if keyword in path:
                score += value

        for keyword, value in self.NEGATIVE_PATH_KEYWORDS.items():
            if keyword in path:
                score += value

        score += self.SOURCE_BONUS.get(candidate.source, 0)

        candidate.score = score

        return candidate