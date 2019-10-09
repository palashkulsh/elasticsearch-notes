for i in  mktorders-555; do  echo "curl -XPUT -H \"Content-Type: application/json\" localhost:9200/$i/_settings -d'{\"index.routing.allocation.include.box_type\":\"warm\"}'"; done;
