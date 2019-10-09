#deletes item status 1 items from indices
echo "curl -H \"Content-Type: application/json\" -XGET  localhost:9200/$1/_count  -d'{\"query\":{\"bool\":{\"must\":[{\"terms\":{\"payment_status\":[4]}},{\"range\":{\"created_at\":{\"lt\":\"now-6M\"}}}]}}}'"
echo "\n"
echo "curl -H \"Content-Type: application/json\" -XPOST  localhost:9200/$1/_delete_by_query?wait_for_completion=false  -d'{\"query\":{\"bool\":{\"must\":[{\"terms\":{\"payment_status\":[4]}},{\"range\":{\"created_at\":{\"lt\":\"now-6M\"}}}]}}}'"
