from app.modules.torznab import TorznabClient


client = TorznabClient(
    "http://jackett:9117/api/v2.0/indexers/all/results/torznab/api",
    "of6a05kndn50fdq27313zfw3l66yn3cj"
)


results = client.search(
    "Game.of.Thrones.S01E01"
)


print("Found:", len(results))


for r in results[:5]:

    print("\nTITLE:", r.title)
    print("HASH:", r.info_hash)
    print("SIZE:", r.size_bytes)
    print("SEEDS:", r.seeders)
    print("MAGNET:", r.magnet[:80])
