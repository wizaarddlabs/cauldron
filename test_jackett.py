from app.modules.torznab import TorznabClient


client = TorznabClient()


results = client.search(
    "Game.of.Thrones.S01E01"
)


for r in results[:10]:

    print("----------------")
    print(r["title"])
    print(
        "Seeds:",
        r["seeders"]
    )

