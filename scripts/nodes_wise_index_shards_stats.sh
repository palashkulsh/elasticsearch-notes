curl -s -XGET localhost:9200/_cat/shards?h=node | sort|uniq -c | sort -k2
