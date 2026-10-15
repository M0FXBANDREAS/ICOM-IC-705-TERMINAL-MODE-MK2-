def safe_emit(signal, *args):
    try:
        signal.emit(*args)
    except RuntimeError:
        pass
