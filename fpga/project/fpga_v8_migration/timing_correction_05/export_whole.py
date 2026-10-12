"""V7 physical/STA export; retained TC04/TC02 implementation with exact edits."""
from reuse import load


def main():
    load('export_whole.py', record=True)['main']()


if __name__ == '__main__':
    main()
