#curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d '{"transient":{"cluster.routing.allocation.cluster_concurrent_rebalance":10}}'

#####for adding nodes and speeding up the rebalance
#curl -H "Content-Type: application/json" -XPUT localhost:9200/_cluster/settings -d '{"transient": {"cluster.routing.allocation.node_concurrent_recoveries": 10}}'
