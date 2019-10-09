host=`node -e "host=['','pawslmktorderes04','pawslmktorderes05','pawslmktorderes07'];index=Math.ceil(Math.random()*(host.length-1));console.log(host[index])"`
echo "curl -H \"Content-Type: application/json\" -XPOST \"$host:9200/_reindex?wait_for_completion=false\" -d '{\"conflicts\": \"proceed\",\"source\": {\"remote\": {\"socket_timeout\": \"2m\",\"host\": \"http://10.0.45.65:80\"},\"index\": \"$1\"},\"dest\": {\"index\": \"$1\",\"type\": \"doc\"}}'"
echo "\n"
echo "curl -H \"Content-Type: application/json\" -XPUT $host:9200/"$1"/_settings -d '{\"index\":{\"number_of_replicas\":0,\"refresh_interval\":\"30s\"}'}"
echo "\n************************************************\n"
