# BasketStatsAssistant

## Docker Environment

```bash
docker build . -t basket_stats_assistant:1.0.0
docker run --rm -it --env-file ./dockerEnvironment/env.list --name basket_stats_assistant \
  -v "$(pwd)/data":/basket_stats_assistant/data \
  -v "$(pwd)/src":/basket_stats_assistant/src \
  basket_stats_assistant:1.0.0 /bin/bash
```
