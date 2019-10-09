###for getting which index has what many replicas and which box_type does it reside on
curl -s -XGET localhost:9200/_cat/indices?h=index | grep mkt | xargs -I {} sh -c "curl -s -XGET localhost:9200/{}/_settings?pretty | jq '.[] | \"\(.settings.index.provided_name),\(.settings.index.routing.allocation.include.box_type),\(.settings.index.refresh_interval),\(.settings.index.number_of_shards),\(.settings.index.number_of_replicas)\"'" | sed 's/"//g' | sort
