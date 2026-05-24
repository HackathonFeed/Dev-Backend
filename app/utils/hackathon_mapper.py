from app.models.hackathon_model import Hackathon
from app.schemas.hackathon_schema import HackathonResponse
from app.utils.hackathon_status_utils import derive_registration_status, registration_status_label


def to_hackathon_response(hackathon: Hackathon) -> HackathonResponse:
    status = derive_registration_status(
        start_date=hackathon.start_date,
        end_date=hackathon.end_date,
        deadline=hackathon.deadline,
    )
    response = HackathonResponse.model_validate(hackathon)
    return response.model_copy(
        update={
            "status": status,
            "status_label": registration_status_label(status, start_date=hackathon.start_date),
        }
    )
