from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from care_maternal import eka


class EkaTokenView(APIView):
    """Staff only: a short-lived Eka Care access token for the scribe.

    ?renew=1 asks for a new token (the scribe sends it after Eka answered 401).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        token = eka.access_token(force=request.query_params.get("renew") == "1")
        response = Response(token)
        response["Cache-Control"] = "no-store"
        return response
