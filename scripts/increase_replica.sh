echo "curl -H \"Content-Type: application/json\" -XPUT localhost:9200/"$1"/_settings -d '{\"index\":{\"number_of_replicas\":3}'}"
