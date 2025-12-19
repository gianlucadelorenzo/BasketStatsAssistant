# BasketStatsAssistant

## Docker Environment

```bash
docker build . -t basket_stats_assistant:1.0.0
docker run --rm -it --env-file ./dockerEnvironment/env.list --name basket_stats_assistant \
  -v "$(pwd)/data":/basket_stats_assistant/data \
  -v "$(pwd)/src":/basket_stats_assistant/src \
  basket_stats_assistant:1.0.0 /bin/bash
```

## Script Execution 

```bash
cd basket_stats_assistant/
python src/sbobina.py data/20251214_PalestrePertini_PVvsANZOLA/ --model-size medium --device cpu --language it
python src/analizza.py data/20251214_PalestrePertini_PVvsANZOLA/
python src/aggrega.py data/20251214_PalestrePertini_PVvsANZOLA/ --roster data/formazione_PV.txt
```