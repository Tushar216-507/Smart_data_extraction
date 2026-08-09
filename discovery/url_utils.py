from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
import re

class URLCanonicalizer:
    """Canonicalizes URLs to improve deduplication."""
    
    @staticmethod
    def canonicalize(url: str) -> str:
        if not url:
            return ""
            
        try:
            parsed = urlparse(url)
            
            # Lowercase scheme and netloc
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()
            
            # Remove default ports
            if (scheme == "http" and netloc.endswith(":80")) or (scheme == "https" and netloc.endswith(":443")):
                netloc = netloc.split(":")[0]
                
            # Normalize path (remove trailing slashes except for root, remove multiple slashes)
            path = parsed.path
            path = re.sub(r"//+", "/", path)
            if len(path) > 1 and path.endswith("/"):
                path = path[:-1]
                
            # Sort query parameters
            query = ""
            if parsed.query:
                query_params = parse_qsl(parsed.query, keep_blank_values=True)
                query_params.sort(key=lambda x: x[0])
                query = urlencode(query_params)
                
            # Remove fragment entirely (fragments just point to a section on the same page)
            fragment = ""
            
            return urlunparse((scheme, netloc, path, parsed.params, query, fragment))
            
        except Exception:
            return url


class ConservativeFilter:
    """
    Conservatively filters URLs that are almost certainly not programmes.
    Avoids filtering academic paths or possible semester pages.
    """
    
    # Extensions that are never HTML programme pages
    BLOCKED_EXTENSIONS = {
        ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", 
        ".zip", ".tar", ".gz", ".rar", ".mp4", ".mp3", ".doc", ".docx", 
        ".xls", ".xlsx", ".ppt", ".pptx", ".xml", ".json", ".csv"
    }
    
    # Paths that are almost certainly not programmes
    BLOCKED_PATHS = {
        "/news", "/events", "/staff", "/faculty-staff", "/login", "/admin", 
        "/directory", "/contact", "/about-us", "/privacy", "/terms",
        "/cookie-policy", "/press", "/alumni", "/library"
    }
    
    @classmethod
    def is_valid(cls, url: str) -> bool:
        if not url:
            return False
            
        try:
            parsed = urlparse(url)
            path = parsed.path.lower()
            
            # 1. Check extensions
            for ext in cls.BLOCKED_EXTENSIONS:
                if path.endswith(ext):
                    return False
                    
            # 2. Check explicitly blocked paths (exact match or path prefix)
            for blocked in cls.BLOCKED_PATHS:
                if path == blocked or path.startswith(f"{blocked}/"):
                    return False
                    
            return True
        except Exception:
            # If we can't parse it, it's safer to keep it than drop it conservatively
            return True
