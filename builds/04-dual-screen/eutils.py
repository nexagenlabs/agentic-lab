"""NCBI E-utilities, behind the cache.

Builds 01 and 02 stubbed these two functions because the point there was the
loop. Here they are real: ``_pubmed_esearch`` runs a query and returns PMIDs,
``fetch_abstract`` retrieves one record and returns it.

Both go through the cache, so a second run of the same corpus makes no
network call at all. That is not only a courtesy to NCBI. It is what lets the
tests run offline, and it is what makes a screening run reproducible: the
record screened on Tuesday is the record screened on Friday, because it came
from the same cache entry with the same hash.
"""

import os
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cache
import httpx

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Where retrieved records land. Overridable so that the tests can point at the
# committed fixture corpus and never reach the network.
CACHE_DIR = Path(os.environ.get("TRIAGE_CACHE_DIR", "cache"))

# NCBI asks that tools identify themselves and that unkeyed clients stay
# within three requests per second. Both are conditions of use, not advice.
TOOL = "agentic-lab-build-03"
CONTACT = os.environ.get("NCBI_CONTACT_EMAIL", "")
TIMEOUT = 20.0


def _params(**extra: Any) -> dict[str, Any]:
    params = {"db": "pubmed", "tool": TOOL, **extra}
    if CONTACT:
        params["email"] = CONTACT
    key = os.environ.get("NCBI_API_KEY")
    if key:
        params["api_key"] = key
    return params


def _pubmed_esearch(query: str, retmax: int = 20) -> list[str]:
    """Return the PMIDs matching ``query``, most recent first.

    The stub in Builds 01 and 02 had this signature. The signature is what the
    rest of the code depended on, which is why only the body changed.
    """
    response = httpx.get(
        f"{EUTILS}/esearch.fcgi",
        params=_params(term=query, retmax=retmax, retmode="xml"),
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    root = ET.fromstring(response.text)
    return [node.text or "" for node in root.findall(".//IdList/Id")]


def _parse_efetch(xml_text: str, pmid: str) -> dict[str, Any] | None:
    """Pull one record out of an efetch response, or None if it is not there."""
    root = ET.fromstring(xml_text)
    article = root.find(".//PubmedArticle")
    if article is None:
        return None

    def text_of(path: str) -> str:
        node = article.find(path)
        return (node.text or "").strip() if node is not None else ""

    # An abstract may arrive in labelled sections. Joining them in document
    # order reproduces what a reader sees, which is what gets screened.
    parts = []
    for node in article.findall(".//Abstract/AbstractText"):
        label = node.get("Label")
        body = "".join(node.itertext()).strip()
        parts.append(f"{label}: {body}" if label else body)

    types = [
        (node.text or "").strip()
        for node in article.findall(".//PublicationTypeList/PublicationType")
    ]

    return {
        "status": "ok",
        "pmid": pmid,
        "title": "".join(article.find(".//ArticleTitle").itertext()).strip()
        if article.find(".//ArticleTitle") is not None
        else "",
        "abstract": " ".join(parts).strip(),
        "journal": text_of(".//Journal/Title"),
        "year": int(text_of(".//JournalIssue/PubDate/Year") or 0) or None,
        "publication_types": types,
        "source": "pubmed-efetch",
    }


def _efetch(pmid: str) -> dict[str, Any]:
    """Retrieve one record from PubMed."""
    response = httpx.get(
        f"{EUTILS}/efetch.fcgi",
        params=_params(id=pmid, retmode="xml"),
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    record = _parse_efetch(response.text, pmid)
    if record is None:
        return {"status": "error", "code": "not_found", "pmid": pmid}
    return record


def fetch_abstract(
    pmid: str,
    *,
    cache_dir: str | Path | None = None,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return one record, from the cache if it is there.

    A cache hit makes no network call, which is the property the tests rely on
    and the reason a re-run costs nothing. Failures are not cached: a record
    that was unavailable this morning may be available this afternoon, and a
    cached failure would be indistinguishable from a real absence for ever.
    """
    cache_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR

    cached = cache.read(pmid, cache_dir)
    if cached is not None:
        return cached

    record = (fetcher or _efetch)(pmid)
    if record.get("status") == "ok":
        cache.write(pmid, record, cache_dir)
    return record
