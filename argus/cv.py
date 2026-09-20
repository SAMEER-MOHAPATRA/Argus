"""
cv.py — turns pasted text into the five setup answers.

Two shapes go through one door, `read`:
  1. the five-line answer from PROMPT (any chatbot) — parsed exactly;
  2. a raw CV — a keyword extractor guesses titles, skills, country, cities.

The extractor is a dictionary match, not a parser. It finds common market
titles and tools; the prompt path gives better titles for unusual roles.
"""

import re

# keep in sync with docs/profile-prompt.md (tests.py checks)
PROMPT = """Read my CV below. Return exactly five lines, nothing else:

titles: <3 to 5 job titles I should search for, comma-separated, lowercase, most wanted first. Use the common market wording, not my past employer's wording.>
country: <the two-letter ISO code of the country I most likely want to work in: US, GB, CA, AU, IN, SG, IE, NZ, DE, NL, AE, or ZA>
remote: <true or false — true if remote work fits my profile>
skills: <8 to 12 tools, languages, or methods from my CV that appear in job postings, comma-separated, lowercase>
locations: <cities or regions I am tied to, comma-separated, or leave empty>

CV:
"""

# common market titles, lowercase; order is the tie-break when counts are equal
TITLES = (
    "software engineer", "software developer", "backend engineer", "backend developer",
    "frontend engineer", "frontend developer", "full stack developer", "full stack engineer",
    "web developer", "mobile developer", "android developer", "ios developer",
    "devops engineer", "site reliability engineer", "cloud engineer", "platform engineer",
    "qa engineer", "test engineer", "automation engineer", "security engineer",
    "data analyst", "business analyst", "data scientist", "data engineer",
    "analytics engineer", "machine learning engineer", "ai engineer", "bi developer",
    "financial analyst", "research analyst", "reporting analyst", "operations analyst",
    "product manager", "project manager", "program manager", "scrum master",
    "product owner", "product designer", "ux designer", "ui designer", "graphic designer",
    "systems engineer", "network engineer", "database administrator", "system administrator",
    "it support", "technical support", "solutions architect", "software architect",
    "mechanical engineer", "electrical engineer", "civil engineer", "chemical engineer",
    "process engineer", "production engineer", "quality engineer", "maintenance engineer",
    "project engineer", "design engineer", "manufacturing engineer", "industrial engineer",
    "metallurgist", "safety officer", "supply chain analyst", "procurement specialist",
    "accountant", "auditor", "tax analyst", "credit analyst", "investment analyst",
    "marketing manager", "digital marketer", "content writer", "seo specialist",
    "sales executive", "account manager", "customer success manager", "recruiter",
    "hr executive", "hr generalist", "operations manager", "nurse", "pharmacist", "teacher",
)

# tools and methods that appear in postings, lowercase. No single letters: "r"
# and "c" match prose. "go" is left out for the same reason; "golang" stays.
SKILLS = (
    "python", "java", "javascript", "typescript", "c++", "c#", ".net", "golang", "rust",
    "kotlin", "swift", "ruby", "php", "scala", "matlab", "bash", "powershell",
    "sql", "mysql", "postgresql", "postgres", "sql server", "oracle", "mongodb", "redis",
    "snowflake", "bigquery", "redshift", "databricks", "spark", "hadoop", "kafka", "airflow",
    "dbt", "etl", "pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "keras",
    "power bi", "tableau", "looker", "excel", "vba", "google sheets", "sas", "spss",
    "react", "angular", "vue", "next.js", "node.js", "django", "flask", "fastapi", "spring",
    "html", "css", "rest", "graphql", "microservices",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ansible", "jenkins",
    "github actions", "ci/cd", "linux", "git", "jira", "confluence",
    "agile", "scrum", "kanban", "six sigma", "lean", "autocad", "solidworks", "catia",
    "sap", "salesforce", "servicenow", "figma", "adobe xd", "photoshop", "illustrator",
    "selenium", "cypress", "playwright", "postman", "pmp", "prince2", "itil",
)

# place name -> country code. Country names first; the rest are cities and
# double as `locations` answers.
COUNTRY_NAMES = {
    "united states": "US", "usa": "US", "united kingdom": "GB", "canada": "CA",
    "australia": "AU", "india": "IN", "singapore": "SG", "ireland": "IE",
    "new zealand": "NZ", "germany": "DE", "netherlands": "NL",
    "united arab emirates": "AE", "uae": "AE", "south africa": "ZA",
}
CITIES = {
    "new york": "US", "san francisco": "US", "seattle": "US", "austin": "US", "chicago": "US",
    "boston": "US", "los angeles": "US", "london": "GB", "manchester": "GB", "edinburgh": "GB",
    "toronto": "CA", "vancouver": "CA", "montreal": "CA", "sydney": "AU", "melbourne": "AU",
    "brisbane": "AU", "pune": "IN", "mumbai": "IN", "bengaluru": "IN", "bangalore": "IN",
    "hyderabad": "IN", "chennai": "IN", "delhi": "IN", "gurgaon": "IN", "gurugram": "IN",
    "noida": "IN", "kolkata": "IN", "ahmedabad": "IN", "dublin": "IE", "auckland": "NZ",
    "wellington": "NZ", "berlin": "DE", "munich": "DE", "hamburg": "DE", "amsterdam": "NL",
    "rotterdam": "NL", "dubai": "AE", "abu dhabi": "AE", "cape town": "ZA",
    "johannesburg": "ZA",
}

_ANSWER_LINE = re.compile(
    r"^\W*(titles|country|remote|skills|locations)\W*:\s*(.*?)\s*$", re.MULTILINE | re.IGNORECASE,
)


def _list(value: str) -> list[str]:
    return [s.strip().lower() for s in value.split(",") if s.strip()]


def _count(term: str, low: str) -> int:
    # letters and digits on either side would make it part of another word;
    # "+", "#" and "." are allowed so "c++", "c#" and ".net" still match
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", low))


def _ranked(terms, low: str, limit: int) -> list[str]:
    counts = {t: _count(t, low) for t in terms}
    return [t for t, n in sorted(counts.items(), key=lambda kv: -kv[1]) if n][:limit]


def parse_answers(text: str) -> dict | None:
    """The five-line answer, with any chatbot chatter around it. None if no `titles:` line."""
    found = {k.lower(): v for k, v in _ANSWER_LINE.findall(text)}
    if "titles" not in found:
        return None
    return {
        "titles": _list(found["titles"]),
        "country": (found.get("country") or "US").strip().upper()[:2],
        "remote": found.get("remote", "true").strip().lower()[:1] in ("t", "y", "1"),
        "skills": _list(found.get("skills", "")),
        "locations": _list(found.get("locations", "")),
    }


def extract_profile(text: str) -> dict:
    """Guess the five answers from a CV. Titles and skills by frequency; country by place names."""
    low = text.lower()
    votes: dict[str, int] = {}
    for place, code in {**COUNTRY_NAMES, **CITIES}.items():
        votes[code] = votes.get(code, 0) + _count(place, low)
    country = max(votes, key=votes.get) if any(votes.values()) else "US"
    return {
        "titles": _ranked(TITLES, low, 5),
        "country": country,
        # ponytail: CVs rarely say "remote"; default on, the form can turn it off
        "remote": True,
        "skills": _ranked(SKILLS, low, 12),
        "locations": _ranked(CITIES, low, 2),
    }


def read(text: str) -> dict:
    """Five answers from either shape of pasted text."""
    return parse_answers(text) or extract_profile(text)
