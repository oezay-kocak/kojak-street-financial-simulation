"""Update option topology only when it changes, preserving open popups."""

from PySide6.QtCore import QSignalBlocker


def patch_combo(combo, options, *, selected=None):
    """Options are (label, data) pairs; identical options do not rebuild rows."""
    if [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())] != options:
        with QSignalBlocker(combo):
            combo.clear()
            for label, data in options:
                combo.addItem(label, data)
    if selected is not None:
        values = [data for _label, data in options]
        index = values.index(selected) if selected in values else 0
        if combo.currentIndex() != index:
            with QSignalBlocker(combo):
                combo.setCurrentIndex(index)
