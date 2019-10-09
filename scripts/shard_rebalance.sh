##ran this command when new node was added but relocation stopped without properly balancing the data among the nodes
### https://www.elastic.co/guide/en/elasticsearch/reference/current/shards-allocation.html
#curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d '{"transient":{"cluster.routing.allocation.balance.shard":"0.75f"}}'

#this handles shards of index across nodes
##curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d '{"transient":{"cluster.routing.allocation.balance.index":"0.85f"}}'
