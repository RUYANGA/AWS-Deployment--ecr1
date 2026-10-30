"""Pagination used by list endpoints across the API."""

from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    """Page-number pagination with a client-adjustable page size.

    Clients request ``?page=<n>`` and may set ``?page_size=<n>`` (capped at 100).
    Responses contain ``count``, ``next``, ``previous`` and ``results``.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
