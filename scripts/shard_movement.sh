echo "curl -H \"Content-Type: application/json\" -XPUT \"localhost:9200/$1/_settings\" -d'{  \"index.routing.allocation.include.box_type\": \"$2\"}'"
