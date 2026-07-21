import re
from urllib.parse import urlparse

from discovery.models import CandidateURL


class URLScorer:
    """
    Evaluates candidate URLs based on multiple URL signals.

    The score is used to rank and filter candidate
    program pages, and acts as an early evaluator in the
    evidence accumulation model.
    """

    POSITIVE_PATH_KEYWORDS = {
        r"\bprograms?\b": 20,
        r"\bcourses?\b": 20,
        r"\bdegrees?\b": 25,
        r"\bstudies\b|\bstudy\b": 20,
        r"\bbachelors?\b": 40,
        r"\bmasters?\b": 40,
        r"\bundergraduate\b": 35,
        r"\bpostgraduate\b": 35,
        r"\bgraduate\b": 25,
        r"\bcatalog(?:ue)?\b": 25,
        r"\bcurriculum\b": 25,
        r"\bmajor\b": 30,
        r"\bminor\b": 25,
        r"\bacademics?\b": 15,
    }

    NEGATIVE_PATH_KEYWORDS = {
        r"\bnews\b": -100,
        r"\bevents?\b": -100,
        r"\bblog\b": -80,
        r"\bpress\b": -80,
        r"\balumni\b": -80,
        r"\bcareers?\b": -60,
        r"\bjobs?\b": -60,
        r"\bstaff\b": -50,
        r"\bpeople\b": -50,
        r"\bcontacts?\b": -50,
        r"\bprivacy\b": -100,
        r"\bcookies?\b": -100,
        r"\blogin\b": -100,
    }

    SOURCE_BONUS = {
        "catalog": 15,
        "navigation": 10,
        "search": 5,
        "sitemap": 5,
        "crawler": 0,
    }

    def score(self, candidate: CandidateURL) -> CandidateURL:
        
        path = urlparse(candidate.url).path.lower()
        
        total_score = 0

        for pattern, value in self.POSITIVE_PATH_KEYWORDS.items():
            if re.search(pattern, path):
                total_score += value
                candidate.add_evidence(
                    f"url_positive_{pattern}", 
                    value, 
                    f"+ URL matched '{pattern}'"
                )

        for pattern, value in self.NEGATIVE_PATH_KEYWORDS.items():
            if re.search(pattern, path):
                total_score += value
                candidate.add_evidence(
                    f"url_negative_{pattern}", 
                    value, 
                    f"- URL matched '{pattern}'"
                )

        source_bonus = self.SOURCE_BONUS.get(candidate.source, 0)
        if source_bonus > 0:
            total_score += source_bonus
            candidate.add_evidence(
                "source_bonus", 
                source_bonus, 
                f"+ Found by {candidate.source}"
            )
            
        candidate.score = total_score

        return candidate