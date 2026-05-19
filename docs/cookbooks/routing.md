# Routing exchanges

A `topic` exchange dispatches messages to different queues based on routing
key patterns (`*` matches a single segment, `#` matches zero-or-more).

Source: [`cookbooks/routing.py`](https://github.com/Sabin2003/LangChain_da/blob/main/cookbooks/routing.py)

```python title="cookbooks/routing.py"
--8<-- "cookbooks/routing.py"
```
