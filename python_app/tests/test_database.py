from database import DatabaseHandler


def test_history_is_lightweight_and_selected_jump_loads_curve(tmp_path):
    db = DatabaseHandler(tmp_path / "jumps.db")
    jump_id = db.save_jump({
        "height_flight": 31.5,
        "height_impulse": 30.0,
        "flight_time": 500,
        "force_curve": [{"t": 1, "v": 70, "p": 0, "vel": 0}],
        "sub_jumps": [{"jump_number": 1, "height_flight": 31.5}],
    })

    history = db.load_history()
    loaded = db.load_jump(jump_id)

    assert history[0]["_id"] == jump_id
    assert history[0]["force_curve"] == []
    assert history[0]["_curve_loaded"] is False
    assert "sub_jumps" not in history[0]
    assert loaded["force_curve"] == [{"t": 1, "v": 70, "p": 0, "vel": 0}]
    assert loaded["sub_jumps"] == [{"jump_number": 1, "height_flight": 31.5}]
    assert loaded["_curve_loaded"] is True


def test_delete_jump_is_durable(tmp_path):
    db = DatabaseHandler(tmp_path / "jumps.db")
    jump_id = db.save_jump({"height_impulse": 12.0})

    assert db.delete_jump(jump_id) == 1
    assert db.load_jump(jump_id) is None
    assert db.load_history() == []
