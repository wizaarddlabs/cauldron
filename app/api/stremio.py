from fastapi import APIRouter, HTTPException

from app.scrapers.aggregator import search_all

router = APIRouter()


def _decode_config(config: str):
    """
    Cauldron currently does not require debrid credentials.
    Keep compatibility with Stremio config URLs.
    """
    return {
        "config": config
    }


@router.get("/{config}/stream/{type}/{id}.json")
async def stream(
    config: str,
    type: str,
    id: str
):

    try:

        print("=== CAULDRON STREAM REQUEST ===", flush=True)
        print("TYPE:", type, flush=True)
        print("ID:", id, flush=True)

        cfg = _decode_config(config)

        parts = id.split(":")

        imdb_id = parts[0]

        season = None
        episode = None


        if type == "series" and len(parts) >= 3:
            season = parts[1]
            episode = parts[2]


        print(
            "SEARCHING:",
            imdb_id,
            season,
            episode,
            flush=True
        )


        torrents = await search_all(
            query=imdb_id,
            imdb_id=imdb_id,
            season=season,
            episode=episode,
            media_type=type
        )


        print(
            "FOUND TORRENTS:",
            len(torrents),
            flush=True
        )


        if not torrents:
            return {
                "streams": []
            }



        # Better episode matching
        if type == "series" and season and episode:

            filtered = []

            s = int(season)
            e = int(episode)

            patterns = [
                f"s{s:02d}e{e:02d}",
                f"s{s}e{e}",
                f"{s}x{e:02d}",
                f"e{e:02d}",
                f"episode {e}",
                f"episode.{e}",
            ]


            for torrent in torrents:

                title = torrent.title.lower()


                if any(
                    pattern.lower() in title
                    for pattern in patterns
                ):
                    filtered.append(torrent)


            torrents = filtered


            print(
                "AFTER EP FILTER:",
                len(torrents),
                flush=True
            )



        output = []


        for torrent in torrents[:25]:

            output.append(
                {
                    "name": "Cauldron",

                    "title": torrent.title,

                    "infoHash": torrent.info_hash,

                    "sources": [
                        f"magnet:{torrent.magnet}"
                    ],

                    "behaviorHints": {
                        "bingeGroup": "cauldron"
                    }
                }
            )


        print(
            "RETURNING STREAMS:",
            len(output),
            flush=True
        )


        return {
            "streams": output
        }



    except Exception as e:

        print(
            "CAULDRON STREAM ERROR:",
            repr(e),
            flush=True
        )

        raise HTTPException(
            500,
            str(e)
        )