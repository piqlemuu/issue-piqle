#!/usr/bin/env python3
"""ISSUE PIQLE offline SEO deployment audit (stdlib only).

Reads only a generated GitHub Pages `site/` directory. Does not modify it.
Checks sitemap, indexability, canonical URLs, titles, and local HTML links.

Default mode is observational: report problems but exit 0 to avoid disrupting
existing 30-minute data collection and deployment. `--strict` exits 1 if an
ERROR is present. Outputs JSON, Markdown, and GitHub Actions annotations.
"""
from __future__ import annotations

import argparse
import html
from html.parser import HTMLParser
import json
import os
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit, unquote, quote
import sys
import xml.etree.ElementTree as ET

DEFAULT_BASE = "https://piqlemuu.github.io/issue-piqle/"
MAX_ANNOTATIONS = 30
MAX_DISPLAY = 80


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = []
        self.in_title = False
        self.h1_count = 0
        self.canonical = []
        self.description = ""
        self.robots = []
        self.hrefs = []
        self.ldjson = []
        self._ld_active = False
        self._ld_buffer = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        tag = tag.lower()
        if tag == "title":
            self.in_title = True
        elif tag == "h1":
            self.h1_count += 1
        elif tag == "link" and "canonical" in (attrs.get("rel") or "").lower().split():
            self.canonical.append(attrs.get("href", ""))
        elif tag == "meta":
            name = (attrs.get("name") or "").lower()
            if name in ("robots", "googlebot"):
                self.robots.append(attrs.get("content", "").lower())
            elif name == "description" and not self.description:
                self.description = (attrs.get("content") or "").strip()
        elif tag == "a" and attrs.get("href"):
            self.hrefs.append(attrs["href"])
        elif tag == "script" and (attrs.get("type") or "").lower() == "application/ld+json":
            self._ld_active = True
            self._ld_buffer = []

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False
        elif tag.lower() == "script" and self._ld_active:
            self._ld_active = False
            self.ldjson.append("".join(self._ld_buffer))
            self._ld_buffer = []

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self._ld_active:
            self._ld_buffer.append(data)

    @property
    def page_title(self):
        return " ".join("".join(self.title).split())

    @property
    def noindex(self):
        return any("noindex" in x for x in self.robots)


class SeoAudit:
    def __init__(self, site: Path, base: str):
        self.site = site.resolve()
        self.base = base.rstrip("/") + "/"
        self.bu = urlsplit(self.base)
        if self.bu.scheme not in ("http", "https") or not self.bu.hostname:
            raise ValueError("--base must be an absolute HTTP(S) URL")
        self.root_path = self.bu.path
        if not self.root_path.endswith("/"):
            raise ValueError("--base must be a directory URL")
        self.pages = {}
        self.issues = []
        self.urls = []
        self.sitemap_targets = set()

    def issue(self, severity, code, path, message):
        self.issues.append(Issue(severity, code, str(path), str(message)))

    def relative_url(self, url):
        """Return a site-root relative path or None for external/nonlocal URLs."""
        if not url or url.startswith(("#", "?")):
            return None
        try:
            parsed = urlsplit(urljoin(self.base, url))
        except ValueError:
            return None
        if parsed.scheme not in ("http", "https") or parsed.netloc.lower() != self.bu.netloc.lower():
            return None
        # Preserve intentionally separate piqlemuu.github.io/ landing page.
        if not parsed.path.startswith(self.root_path):
            return None
        decoded = unquote(parsed.path[len(self.root_path):])
        if "\\" in decoded or any(part == ".." for part in decoded.split("/")):
            return "__INVALID_PATH__"
        return decoded + ("index.html" if not decoded or decoded.endswith("/") else "")

    def url_for(self, local: Path):
        s = local.as_posix()
        if s == "index.html":
            s = ""
        elif s.endswith("/index.html"):
            s = s[:-len("index.html")]
        return self.base + quote(s, safe="/-._~")

    def read_pages(self):
        if not self.site.is_dir():
            self.issue("error", "NO_SITE", "site/", "배포 디렉터리가 없습니다")
            return
        for path in sorted(self.site.rglob("*.html")):
            rel = path.relative_to(self.site)
            try:
                parser = PageParser()
                parser.feed(path.read_text(encoding="utf-8"))
                parser.close()
                self.pages[rel.as_posix()] = parser
            except (OSError, UnicodeDecodeError) as exc:
                self.issue("error", "HTML_READ_ERROR", rel, str(exc))
        if not self.pages:
            self.issue("error", "NO_HTML", "site/", "HTML 파일이 없습니다")

    def check_sitemap(self):
        sitemap = self.site / "sitemap.xml"
        if not sitemap.is_file():
            self.issue("error", "NO_SITEMAP", "sitemap.xml", "사이트맵 파일이 없습니다")
            return
        try:
            root = ET.parse(sitemap).getroot()
        except (ET.ParseError, OSError) as exc:
            self.issue("error", "INVALID_XML", "sitemap.xml", f"사이트맵 XML 파싱 실패: {exc}")
            return
        if root.tag.rsplit("}", 1)[-1] != "urlset":
            self.issue("error", "NOT_URLSET", "sitemap.xml", "<urlset> 형식의 사이트맵이 아닙니다")
            return
        seen = set()
        for item in root:
            if item.tag.rsplit("}", 1)[-1] != "url":
                continue
            loc = next((el.text or "" for el in item if el.tag.rsplit("}", 1)[-1] == "loc"), "").strip()
            if not loc:
                self.issue("error", "EMPTY_LOC", "sitemap.xml", "URL 항목에 loc가 없습니다")
                continue
            self.urls.append(loc)
            if loc in seen:
                self.issue("error", "DUPLICATE_SITEMAP_URL", "sitemap.xml", f"중복 URL: {loc}")
            seen.add(loc)
            local = self.relative_url(loc)
            if local is None:
                self.issue("error", "OUTSIDE_SITE", "sitemap.xml", f"사이트 범위 밖의 URL: {loc}")
                continue
            if local == "__INVALID_PATH__":
                self.issue("error", "INVALID_PATH", "sitemap.xml", f"잘못된 경로: {loc}")
                continue
            self.sitemap_targets.add(local)
            if local not in self.pages:
                self.issue("error", "SITEMAP_404", "sitemap.xml", f"목록에 있지만 HTML 파일이 없음: {loc}")
            else:
                p = self.pages[local]
                if p.noindex:
                    self.issue("error", "SITEMAP_NOINDEX", local, "사이트맵 등록 페이지에 noindex가 설정됨")
        if not self.urls:
            self.issue("error", "EMPTY_SITEMAP", "sitemap.xml", "사이트맵에 URL이 없습니다")

    def check_pages(self):
        # Key pages expected after the four existing generators complete.
        expected = ["index.html", "content.html", "youtube-trending.html", "m/index.html", "i/index.html"]
        for rel in expected:
            if rel not in self.pages:
                self.issue("error", "MISSING_KEY_PAGE", rel, "배포 필수 페이지가 생성되지 않았습니다")
        seen_titles = defaultdict(list)
        seen_canonical = defaultdict(list)
        for rel, page in self.pages.items():
            if not page.noindex:
                if not page.page_title:
                    self.issue("warning", "MISSING_TITLE", rel, "검색 대상 페이지에 title이 없습니다")
                else:
                    seen_titles[page.page_title.casefold()].append(rel)
                if not page.description:
                    self.issue("warning", "MISSING_DESCRIPTION", rel, "검색 대상 페이지에 meta description이 없습니다")
                if not page.h1_count:
                    self.issue("warning", "MISSING_H1", rel, "검색 대상 페이지에 H1이 없습니다")
                elif page.h1_count > 1:
                    self.issue("warning", "MULTIPLE_H1", rel, f"H1이 {page.h1_count}개입니다")
            if len(page.canonical) > 1:
                self.issue("error", "MULTIPLE_CANONICAL", rel, f"canonical이 {len(page.canonical)}개입니다")
            if not page.canonical and not page.noindex:
                self.issue("warning", "MISSING_CANONICAL", rel, "canonical 대표 주소가 없습니다")
            for link in page.canonical:
                if not link:
                    self.issue("error", "EMPTY_CANONICAL", rel, "canonical 주소가 비어 있습니다")
                    continue
                absolute = urljoin(self.url_for(Path(rel)), link)
                target = self.relative_url(absolute)
                if target is None or target == "__INVALID_PATH__":
                    self.issue("error", "INVALID_CANONICAL", rel, f"사이트 범위 밖 또는 잘못된 대표 URL: {link}")
                elif not page.noindex:
                    seen_canonical[target].append(rel)
                    if target != rel:
                        # /m/ and /m/index.html point to the same local file, already normalized.
                        self.issue("warning", "CANONICAL_MISMATCH", rel, f"자신이 아닌 페이지를 대표 URL로 선언: {link}")
            for n, script in enumerate(page.ldjson, start=1):
                try:
                    json.loads(script.strip())
                except json.JSONDecodeError as exc:
                    self.issue("warning", "BAD_JSON_LD", rel, f"구조화 데이터 {n}번 JSON 오류: {exc.msg}")
        for title, items in seen_titles.items():
            if len(items) > 1:
                self.issue("warning", "DUPLICATE_TITLE", ", ".join(items[:3]), f"같은 SEO title이 {len(items)}개 페이지에 사용됨: {title[:90]}")
        for target, items in seen_canonical.items():
            if len(set(items)) > 1:
                self.issue("warning", "SHARED_CANONICAL", ", ".join(items[:3]), f"여러 페이지가 같은 canonical을 가리킴: {target}")
        for rel in ("youtube-trending.html", "m/index.html", "i/index.html"):
            if rel in self.pages and not self.pages[rel].noindex and rel not in self.sitemap_targets:
                self.issue("warning", "KEY_PAGE_NOT_SITEMAP", rel, "검색 대상 주요 페이지가 사이트맵에 없습니다")

    def check_links(self):
        for rel, page in self.pages.items():
            file_url = self.url_for(Path(rel))
            for href in set(page.hrefs):
                href = href.strip()
                if not href or href.startswith(("#", "?", "javascript:", "mailto:", "tel:", "data:")):
                    continue
                local = self.relative_url(urljoin(file_url, href))
                if not local or local == "__INVALID_PATH__":
                    continue
                local_rel = Path(local)
                if not (self.site / local_rel).is_file():
                    self.issue("warning", "BROKEN_INTERNAL_LINK", rel, f"존재하지 않는 내부 링크: {href}")

    def run(self):
        self.read_pages()
        if self.pages:
            self.check_sitemap()
            self.check_pages()
            self.check_links()
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "base": self.base,
            "scanned_html": len(self.pages),
            "sitemap_urls": len(self.urls),
            "counts": {s: sum(i.severity == s for i in self.issues) for s in ("error", "warning", "info")},
            "issues": [asdict(i) for i in self.issues],
            "note": "정적 배포 파일 기준 검사이며 실제 Google Search Console 크롤링 성공을 확인하지는 않습니다.",
        }


def markdown(report):
    n = report["counts"]
    lines = ["## ISSUE PIQLE · 자동 SEO 검사", "",
             f"- HTML 검사: **{report['scanned_html']}개**",
             f"- 사이트맵 URL: **{report['sitemap_urls']}개**",
             f"- 오류: **{n['error']}개** · 개선 권고: **{n['warning']}개**", "",
             "| 분류 | 파일 | 내용 |", "|---|---|---|"]
    for i in report["issues"][:MAX_DISPLAY]:
        msg = str(i["message"]).replace("|", "\\|").replace("\n", " ")
        path = str(i["path"]).replace("|", "\\|")
        lines.append(f"| {i['severity']} · {i['code']} | `{path}` | {msg} |")
    if len(report["issues"]) > MAX_DISPLAY:
        lines.append(f"\n나머지 {len(report['issues']) - MAX_DISPLAY}건은 JSON 파일에서 확인하세요.")
    if not report["issues"]:
        lines.append("| 완료 | — | 검사 항목에서 문제가 발견되지 않았습니다. |")
    lines.extend(["", "> **참고:** 이 도구는 생성된 파일과 링크를 검증합니다. 검색 색인·애드센스 승인·외부 사이트 접근 가능 여부는 별개입니다."])
    return "\n".join(lines) + "\n"


def gha_escape(msg):
    return str(msg).replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--site", default="site", help="Generated site directory")
    ap.add_argument("--base", default=os.getenv("ISSUEPIQLE_BASE_URL", DEFAULT_BASE))
    ap.add_argument("--output", default="seo-audit-report.json", help="JSON report path")
    ap.add_argument("--summary", default="seo-audit-report.md", help="Markdown report path")
    ap.add_argument("--strict", action="store_true", help="Fail when audit has ERRORs")
    args = ap.parse_args(argv)
    report = SeoAudit(Path(args.site), args.base).run()
    output = Path(args.output)
    summary = Path(args.summary)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary_text = markdown(report)
    summary.write_text(summary_text, encoding="utf-8")
    if os.getenv("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as out:
            out.write(summary_text + "\n")
    for issue in report["issues"][:MAX_ANNOTATIONS]:
        level = "error" if issue["severity"] == "error" else "warning"
        message = gha_escape(f"{issue['code']}: {issue['message']}")
        name = gha_escape(issue["path"])
        if "," in issue["path"]:
            print(f"::{level}::{message} ({name})")
        else:
            print(f"::{level} file={name}::{message}")
    counts = report["counts"]
    print(f"[SEO AUDIT] HTML={report['scanned_html']}, sitemap URLs={report['sitemap_urls']}, errors={counts['error']}, warnings={counts['warning']}")
    if len(report["issues"]) > MAX_ANNOTATIONS:
        print(f"[SEO AUDIT] {len(report['issues']) - MAX_ANNOTATIONS} additional findings in {output}")
    if args.strict and counts["error"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
