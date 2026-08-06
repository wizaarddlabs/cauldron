#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from app.filtering.pipeline import FilterPipeline
from app.models import TorrentResult


def main():
    t1 = TorrentResult(title='Movie 2160p HDR x265', info_hash='a'*40, magnet='mag', source='scraper', seeders=100)
    T2 = TorrentResult(title='Movie 1080p x264', info_hash='b'*40, magnet='m2', source='scraper', seeders=2)
    t3 = TorrentResult(title='Movie CAM',    info_hash='c'*40, magnet='m3', source='scraper', seeders=10)

    p = FilterPipeline({'resolution': ['2160p','1080p'], 'min_seeders': 5})
    print('filtered (res+seeders):', [t.title for t in p.apply([t1, T2, t3])])

    # Test codec filtering
    p_codec = FilterPipeline({'codec': ['hevc']})
    print('filtered (codec=hevc):', [t.title for t in p_codec.apply([t1, T2, t3])])

    # Test language filtering
    t_en = TorrentResult(title='Some Movie [English] 1080p', info_hash='d'*40, magnet='m4', source='scraper', seeders=10)
    t_es = TorrentResult(title='Pelicula [Español] 1080p', info_hash='e'*40, magnet='m5', source='scraper', seeders=10)
    p_lang = FilterPipeline({'language': ['english']})
    print('filtered (language=english):', [t.title for t in p_lang.apply([t_en, t_es])])

    # no-config returns all
    print('all:', [t.title for t in FilterPipeline({}).apply([t1, T2, t3])])


if __name__ == '__main__':
    main()
