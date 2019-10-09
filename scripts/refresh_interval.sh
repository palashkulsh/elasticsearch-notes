echo "curl -H \"Content-Type: application/json\" -XPUT localhost:9200/"$1"/_settings -d '{\"refresh_interval\":\"10s\"}'}"
