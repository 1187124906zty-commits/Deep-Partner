"""Verify that a reader without JavaScript can discover actual UI evidence."""
from html.parser import HTMLParser
import json
import urllib.request

BASE = "https://tutor.example.invalid"
client = urllib.request.build_opener(
    urllib.request.ProxyHandler({"https": "http://127.0.0.1:12000"}))


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.hidden = 0
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.text.append(data)


def read(path):
    with client.open(BASE + path, timeout=30) as response:
        return response.read()


def main():
    parser = VisibleText()
    parser.feed(read("/admin/").decode())
    body = " ".join(parser.text)
    print(json.dumps({"http_reader_visible_characters": len(body),
                      "visible_excerpt": body[:300]}, ensure_ascii=True))
    assert "真实界面" in body, "The anonymous HTML reader receives an empty SPA shell"
    review = read("/admin/review").decode()
    assert "研究总览" in review and "<img " in review
    manifest = json.loads(read("/admin/review.json"))
    assert len(manifest["pages"]) >= 6
    for page in manifest["pages"]:
        assert len(page["visible_text"]) > 30
        assert read(page["image_path"]).startswith(b"\x89PNG\r\n\x1a\n")
    print(json.dumps({"passed": True, "rendered_pages": len(manifest["pages"]),
                      "captured_at": manifest["captured_at"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
