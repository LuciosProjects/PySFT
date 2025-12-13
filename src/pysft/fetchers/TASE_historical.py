from pysft.core.structures import indicatorRequest

def fetch_TASE_historical(request: indicatorRequest):
    """
    Fetch historical data for the given indicator using TASE historical fetcher.

    Args:
        request (indicatorRequest): The request object containing indicator details.
    Returns:
        None: The function updates the request object in place.
    """

    # Implementation to fetch data using TASE historical fetcher would go here

    request.success = False  # Placeholder for actual success status

    ...