from src.database import SessionLocal, ListingOpportunity

platforms = [
    ("producthunt", "https://www.producthunt.com/posts/new"),
    ("alternativeto", "https://alternativeto.net/software/create/"),
    ("betalist", "https://betalist.com/submit"),
    ("capterra", "https://www.capterra.com/vendors/add-your-product"),
    ("g2", "https://www.g2.com/products/new"),
    ("softwaresuggest", "https://www.softwaresuggest.com/add-listing"),
    ("getapp", "https://www.getapp.com/vendors/"),
    ("crozdesk", "https://crozdesk.com/vendors/register"),
    ("financesonline", "https://financesonline.com/add-product/"),
    ("trustradius", "https://www.trustradius.com/vendors/add"),
    ("sourceforge", "https://sourceforge.net/projects/new/"),
    ("slant", "https://www.slant.co/add-product"),
    ("stackshare", "https://stackshare.io/tools/new"),
]

db = SessionLocal()
count = 0

for name, url in platforms:
    existing = db.query(ListingOpportunity).filter(ListingOpportunity.url == url).first()
    if not existing:
        # ✅ Sahi column names use karo
        opp = ListingOpportunity(
            url=url,
            domain=name,  # 'platform' nahi, 'domain' hai
            competitors_found="toptal,turing,upwork",
            status="discovered",
            # generated_pitch optional hai, agar column hai toh
        )
        db.add(opp)
        count += 1
        print(f"✅ Added: {name}")

db.commit()
db.close()

print(f"\n🎯 {count} product platforms added!")
print("👉 Now refresh dashboard and go to 'Listing Pitcher' tab")