"""Utility functions for the service module."""


def calculate_savings(start_size: int, end_size: int) -> float:
    """Calculate the percentage savings between start and end sizes.

    Args:
        start_size (int): The initial size.
        end_size (int): The final size.

    Returns:
        float: The percentage savings.

    """
    if start_size == 0:
        return 0.0
    return (start_size - end_size) / start_size * 100
