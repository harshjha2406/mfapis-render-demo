"""Synthetic offline tests. Never call SiftingIO or access Render secrets."""
from datetime import datetime, timezone
from types import SimpleNamespace
import json
import time

import pytest

from mfapis import sifting_stream as stream


def tick(**changes):
    obj = {"f":"tick", "class":"fx", "s":"EURUSD", "b":"1.11200", "a":"1.11222", "t":int(time.time()*1000)}
    obj.update(changes)
    return obj


def test_valid_quote():
    assert stream.validate_tick(tick())[0] == "EUR/USD"


@pytest.mark.parametrize("bad", [
    {"f":"ack"}, {"class":"stocks"}, {"s":"XYZUSD"},
    {"b":"NaN"}, {"a":"Infinity"}, {"b":"1.5", "a":"1.2"},
    {"b":"0"}, {"t":True}, {"t":1234}, {"t":int((time.time()-300)*1000)},
])
def test_bad_quote_rejected(bad):
    assert stream.validate_tick(tick(**bad)) is None


def test_no_writer_when_disabled(monkeypatch):
    monkeypatch.delenv("SIFTING_WS_ENABLED", raising=False)
    assert stream.settings() is None
    stop = stream.start_worker()
    assert not stop.is_set()


def test_invalid_db_config_keeps_collector_off(monkeypatch):
    monkeypatch.setenv("SIFTING_WS_ENABLED", "true")
    monkeypatch.setenv("SIFTING_API_KEY", "test-key-do-not-use")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/not-production.sqlite")
    assert stream.settings() is None


def test_no_secret_exposure_in_logs(monkeypatch, caplog):
    monkeypatch.setenv("SIFTING_WS_ENABLED", "true")
    monkeypatch.setenv("SIFTING_API_KEY", "private-value-test")
    monkeypatch.setenv("DATABASE_URL", "postgresql://worker:private-password@localhost:5432/test")
    monkeypatch.setenv("SIFTING_MIN_WRITE_SECONDS", "30")
    assert stream.settings() is not None
    assert "private-password" not in caplog.text and "private-value-test" not in caplog.text


def test_minimum_write_throttle(monkeypatch):
    calls=[]
    monkeypatch.setattr(stream.fx, "ingest", lambda engine,pair,bid,ask,ts,source: (calls.append((pair,source)) or {"status":"accepted"}), raising=False)
    writes={}
    assert stream.handle_tick(tick(), object(), writes, monotonic=100, write_gap=30)
    assert not stream.handle_tick(tick(), object(), writes, monotonic=105, write_gap=30)
    assert stream.handle_tick(tick(), object(), writes, monotonic=135, write_gap=30)
    assert calls==[("EUR/USD","siftingio_reference")]*2


def test_bad_data_does_not_reach_storage(monkeypatch):
    monkeypatch.setattr(stream.fx, "ingest", lambda *args,**kwargs: pytest.fail("Bad quote reached ingestion"), raising=False)
    assert not stream.handle_tick(tick(b="bad"), object(), {})


def test_websocket_subscription_and_first_tick(monkeypatch):
    import websocket
    n=int(time.time()*1000)
    class Sock:
        def __init__(self): self.frames=[json.dumps(tick(t=n)),''];self.sent=[];self.closed=False
        def send(self,s): self.sent.append(json.loads(s))
        def recv(self): return self.frames.pop(0)
        def close(self): self.closed=True
    socket=Sock()
    class Engine:
        def __init__(self):self.closed=False
        def dispose(self):self.closed=True
    engine=Engine()
    monkeypatch.setattr(stream, "connect", lambda u,initialize=False: engine)
    monkeypatch.setattr(stream, "handle_tick", lambda *args,**kwargs: True)
    import threading
    assert stream.receive_session(threading.Event(), "do-not-log", "postgresql://db", 30, socket_factory=lambda key:socket)
    assert socket.sent[0] == {"op":"subscribe", "product":"fx", "symbols":["EURUSD","GBPUSD","USDJPY","USDCHF","AUDUSD"]}
    assert socket.closed and engine.closed
