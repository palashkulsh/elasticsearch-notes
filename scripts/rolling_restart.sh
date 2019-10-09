sudo vi /etc/elasticsearch/elasticsearch.yml

curl -XPOST localhost:9200/_flush/synced && curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d'{    "transient" : {        "cluster.routing.allocation.enable" : "none"    }}' && sudo service elasticsearch restart 

curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d'{    "transient" : {        "cluster.routing.allocation.enable" : "all"    }}' && watch curl -s -XGET localhost:9200/_cluster/health?pretty
