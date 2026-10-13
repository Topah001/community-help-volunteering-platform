# Neighborly — Community Help and Volunteering Platform

A local, lightweight community board built with Python 3.13, SQLite, and the standard library. It lets neighbors post help requests and volunteer offers, browse and filter posts, see lightweight category/neighborhood matches, and update a post through open → coordinating → resolved.

## Run

```powershell
python app.py
```

Open <http://127.0.0.1:8000>. Data is stored in `community.db` beside the app. Set `COMMUNITY_DB` to use a different SQLite file. Stop with Ctrl+C.

## Privacy and safe use

The sample posts are fictional. This local demo does not collect contact details or display a person's exact location. Use only a general neighborhood label. Matching is a suggestion based only on shared category or area, not a background check or guarantee. Do not post addresses, phone numbers, health information, or other sensitive personal data. Coordinate cautiously, verify details yourself, and choose public meeting places.

## Tests

```powershell
python -m unittest -v
```

No third-party packages are required.
