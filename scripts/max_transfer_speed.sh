curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d'{    "transient" : {        "indices.recovery.max_bytes_per_sec" : "200mb"    }}'
