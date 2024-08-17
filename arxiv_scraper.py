from __future__ import print_function
import xml.etree.ElementTree as ET
import datetime
import time
import sys
from typing import Dict, List

PYTHON3 = sys.version_info[0] == 3
if PYTHON3:
    from urllib.parse import urlencode
    from urllib.request import urlopen
    from urllib.error import HTTPError
else:
    from urllib import urlencode
    from urllib2 import HTTPError, urlopen

# from .constants import OAI, ARXIV, BASE
OAI = "{http://www.openarchives.org/OAI/2.0/}"
ARXIV = "{http://arxiv.org/OAI/arXiv/}"
BASE = "http://export.arxiv.org/oai2?verb=ListRecords&"

class Record(object):
    def __init__(self, xml_record):
        self.xml = xml_record
        self.id = self._get_text(ARXIV, "id")
        self.url = "https://arxiv.org/abs/" + self.id
        self.title = self._get_text(ARXIV, "title")
        self.abstract = self._get_text(ARXIV, "abstract")
        self.cats = self._get_text(ARXIV, "categories")
        self.created = self._get_text(ARXIV, "created")
        self.updated = self._get_text(ARXIV, "updated")
        self.doi = self._get_text(ARXIV, "doi")
        self.authors = self._get_authors()
        self.affiliation = self._get_affiliation()

    def _get_text(self, namespace: str, tag: str) -> str:
        try:
            return (
                self.xml.find(namespace + tag).text.strip().lower().replace("\n", " ")
            )
        except:
            return ""

    def _get_name(self, parent, attribute) -> str:
        try:
            return parent.find(ARXIV + attribute).text.lower()
        except:
            return "n/a"

    def _get_authors(self) -> List:
        authors_xml = self.xml.findall(ARXIV + "authors/" + ARXIV + "author")
        last_names = [self._get_name(author, "keyname") for author in authors_xml]
        first_names = [self._get_name(author, "forenames") for author in authors_xml]
        full_names = [a + " " + b for a, b in zip(first_names, last_names)]
        return full_names

    def _get_affiliation(self) -> str:
        authors = self.xml.findall(ARXIV + "authors/" + ARXIV + "author")
        try:
            affiliation = [
                author.find(ARXIV + "affiliation").text.lower() for author in authors
            ]
            return affiliation
        except:
            return []

    def output(self) -> Dict:
        d = {
            "title": self.title,
            "id": self.id,
            "abstract": self.abstract,
            "categories": self.cats,
            "doi": self.doi,
            "created": self.created,
            "updated": self.updated,
            "authors": self.authors,
            "affiliation": self.affiliation,
            "url": self.url,
        }
        return d

class Scraper(object):
    def __init__(
        self,
        category: str,
        date_from: str = None,
        date_until: str = None,
        t: int = 30,
        timeout: int = 300,
        filters: Dict[str, List[str]] = {},
    ):
        self.cat = str(category)
        self.t = t
        self.timeout = timeout

        if date_from is None:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            self.f = str(yesterday)
        else:
            self.f = date_from

        if date_until is None:
            self.u = str(yesterday)
        else:
            self.u = date_until

        self.url = (
            BASE
            + "from="
            + self.f
            + "&until="
            + self.u
            + "&metadataPrefix=arXiv&set=%s" % self.cat
        )
        self.filters = filters
        if not self.filters:
            self.append_all = True
        else:
            self.append_all = False
            self.keys = filters.keys()

    def scrape(self) -> List[Dict]:
        t0 = time.time()
        tx = time.time()
        elapsed = 0.0
        url = self.url
        ds = []
        k = 1
        while True:
            print("fetching up to ", 1000 * k, "records...")
            try:
                response = urlopen(url)
            except HTTPError as e:
                if e.code == 503:
                    to = int(e.hdrs.get("retry-after", 30))
                    print("Got 503. Retrying after {0:d} seconds.".format(self.t))
                    time.sleep(self.t)
                    continue
                else:
                    raise
            k += 1
            xml = response.read()
            root = ET.fromstring(xml)
            records = root.findall(OAI + "ListRecords/" + OAI + "record")
            for record in records:
                meta = record.find(OAI + "metadata").find(ARXIV + "arXiv")
                record = Record(meta).output()
                if self.append_all:
                    ds.append(record)
                else:
                    save_record = False
                    for key in self.keys:
                        for word in self.filters[key]:
                            if word.lower() in record[key]:
                                save_record = True

                    if save_record:
                        ds.append(record)

            try:
                token = root.find(OAI + "ListRecords").find(OAI + "resumptionToken")
            except:
                return 1
            if token is None or token.text is None:
                break
            else:
                url = BASE + "resumptionToken=%s" % token.text

            ty = time.time()
            elapsed += ty - tx
            if elapsed >= self.timeout:
                break
            else:
                tx = time.time()

        t1 = time.time()
        print("fetching is completed in {0:.1f} seconds.".format(t1 - t0))
        print("Total number of records {:d}".format(len(ds)))
        return ds

def generate_html(records: List[Dict], filename: str):
    today_date = datetime.date.today() - datetime.timedelta(days=1)
    formatted_date = today_date.strftime("%Y-%m-%d")

    html_content = f"""
    <div id="div_diffusion_papers_list" class="list-papers">
    <div class="date-papers">
    <h6><b>{formatted_date}</b></h6>
    """

    for record in records:
        html_content += f"""
        <p><a href='{record['url']}' target='_blank'>{record['title']}</a><br>
        {', '.join(record['authors'])}
        </p>
        """

    html_content += "</div></div>"

    with open(filename, 'w', encoding='utf-8') as file:
        file.write(html_content)
    print(f"HTML file saved as {filename}")

# 使用示例
if __name__ == "__main__":
    scraper = Scraper(
        category='cs',  # 可以设置为你感兴趣的领域
        filters={'abstract': ['diffusion', 'text to image', 'controlnet']}
    )
    records = scraper.scrape()
    generate_html(records, 'arxiv_papers.html')
