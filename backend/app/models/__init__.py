"""SQLAlchemy model package."""

from app.models.business_extensions import (  # noqa: F401,E402
    PurchaseRequest,
    PurchaseRequestItem,
    PurchaseReturnItem,
    SalesQuote,
    SalesQuoteItem,
    SalesReturnItem,
)
from app.models.platform import ExtEventOutbox, SysApiClient  # noqa: F401,E402
from app.models.collaboration import (  # noqa: F401,E402
    BizAttachment,
    BizComment,
    BizDocument,
    BizDocumentRelation,
    SysIdempotencyRecord,
    SysNotification,
)
from app.models.cost import CostAllocation, CostPeriodClose, CostProjectEntry  # noqa: F401,E402
from app.models.crm import CrmContact, CrmFollowUp, CrmLead, CrmOpportunity  # noqa: F401,E402
from app.models.quality import QaCapaAction, QaInspection, QaNonconformity, QaPlan  # noqa: F401,E402
from app.models.hr import HrAttendance, HrEmployee, HrPayroll  # noqa: F401,E402
from app.models.inventory_advanced import (  # noqa: F401,E402
    InvBatch,
    InvCostLayer,
    InvCostLayerConsumption,
    InvLocation,
    InvSlowMovingRule,
    InvScanRecord,
    InvWarehouseAccess,
    InvZone,
)
from app.models.production import (  # noqa: F401,E402
    MfgBom,
    MfgBomItem,
    MfgCapacityCalendar,
    MfgMaterialIssue,
    MfgMaterialIssueItem,
    MfgMaterialReturn,
    MfgMaterialReturnItem,
    MfgMps,
    MfgMrpResult,
    MfgMrpRun,
    MfgReport,
    MfgRouting,
    MfgRoutingOperation,
    MfgSubcontractOrder,
    MfgSubcontractReceipt,
    MfgWorkOrder,
    MfgWorkOrderMaterial,
    MfgWorkCenter,
)
