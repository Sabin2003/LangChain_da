# RPC

A request/reply pattern using a temporary `reply_to` queue and a unique
`correlation_id` per call. Useful when an agent needs to invoke a remote
service exposed over AMQP.

Source: [`cookbooks/rpc.py`](https://github.com/Sabin2003/LangChain_da/blob/main/cookbooks/rpc.py)

```python title="cookbooks/rpc.py"
--8<-- "cookbooks/rpc.py"
```
