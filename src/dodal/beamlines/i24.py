from functools import cache
from pathlib import Path

from daq_config_server.client import ConfigClient
from ophyd_async.core import (
    AutoMaxIncrementingPathProvider,
    FilenameProvider,
    PathProvider,
    StaticPathProvider,
)

from dodal.common.beamlines.beamline_utils import BL, set_config_client
from dodal.common.beamlines.beamline_utils import set_beamline as set_utils_beamline
from dodal.device_manager import DeviceManager
from dodal.devices.attenuator.attenuator import EnumFilterAttenuator
from dodal.devices.attenuator.filter_selections import (
    I24FilterOneSelections,
    I24FilterTwoSelections,
)
from dodal.devices.beamlines.i24.aperture import Aperture
from dodal.devices.beamlines.i24.beam_center import DetectorBeamCenter
from dodal.devices.beamlines.i24.beamstop import Beamstop
from dodal.devices.beamlines.i24.commissioning_jungfrau import (
    CommissioningJungfrauDetector,
)
from dodal.devices.beamlines.i24.dcm import DCM
from dodal.devices.beamlines.i24.dual_backlight import DualBacklight
from dodal.devices.beamlines.i24.focus_mirrors import FocusMirrorsMode
from dodal.devices.beamlines.i24.pmac import PMAC
from dodal.devices.beamlines.i24.vgonio import VerticalGoniometer
from dodal.devices.hutch_shutter import InterlockedHutchShutter
from dodal.devices.interlocks import PSSInterlock
from dodal.devices.motors import YZStage
from dodal.devices.oav.oav_detector import OAVBeamCentreFile
from dodal.devices.oav.oav_parameters import OAVConfigBeamCentre
from dodal.devices.robot import BartRobot
from dodal.devices.synchrotron import Synchrotron
from dodal.devices.zebra.zebra import Zebra
from dodal.devices.zebra.zebra_constants_mapping import (
    ZebraMapping,
    ZebraSources,
    ZebraTTLOutputs,
)
from dodal.devices.zebra.zebra_controlled_shutter import MXZebraShutter
from dodal.log import set_beamline as set_log_beamline
from dodal.utils import BeamlinePrefix, get_beamline_name

ZOOM_PARAMS_FILE = (
    "/dls_sw/i24/software/gda_versions/gda/config/xml/jCameraManZoomLevels.xml"
)
DISPLAY_CONFIG = "/dls_sw/i24/software/gda_versions/var/display.configuration"

# Base directory for Jungfrau commissioning data. Update this per beamtime; each
# acquisition gets a numbered subdirectory beneath it.
JUNGFRAU_DATA_DIR = Path("/dls/i24/data/2026/cm44177-1/jungfrau")


class _RequestedFilenameProvider(FilenameProvider):
    """The name a plan has asked the commissioning jungfrau to write under.

    Temporary, for as long as i24 writes jungfrau data without numtracker. Numtracker
    takes the name from the `detector_file_template` run metadata, and once blueapi is
    configured with it the path_provider fixture below is replaced and this goes unused.
    Until then nothing carries the requested name to the filewriter, so a plan sets it
    here before collecting and every collection is otherwise called "jungfrau".

    Remove with https://github.com/DiamondLightSource/mx-bluesky/issues/1527.
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename

    def __call__(self, datakey_name: str | None = None) -> str:
        return self.filename


JUNGFRAU_FILENAME = _RequestedFilenameProvider("jungfrau")


BL = get_beamline_name("i24")
set_log_beamline(BL)
set_utils_beamline(BL)
set_config_client(ConfigClient.from_url())

I24_ZEBRA_MAPPING = ZebraMapping(
    outputs=ZebraTTLOutputs(TTL_EIGER=1, TTL_JUNGFRAU=2, TTL_FAST_SHUTTER=4),
    sources=ZebraSources(),
)

PREFIX = BeamlinePrefix(BL)

devices = DeviceManager()


@devices.fixture
@cache
def path_provider() -> PathProvider:
    # A provider that needs no external service, so detectors can write when running
    # outside blueapi or without numtracker configured. When blueapi is configured with
    # numtracker it overrides this fixture with its own StartDocumentPathProvider, which
    # takes filenames from the `detector_file_template` run metadata instead.
    # Note this must not require a device_name, as AutoMaxIncrementingPathProvider (see
    # the jungfrau factory below) calls its base provider without one.
    return StaticPathProvider(
        JUNGFRAU_FILENAME,
        JUNGFRAU_DATA_DIR,
    )


@devices.fixture
@cache
def config_client() -> ConfigClient:
    return ConfigClient.from_url()


@devices.factory()
def attenuator() -> EnumFilterAttenuator:
    return EnumFilterAttenuator(
        f"{PREFIX.beamline_prefix}-OP-ATTN-01:",
        filter_selection=(I24FilterOneSelections, I24FilterTwoSelections),
    )


@devices.factory()
def aperture() -> Aperture:
    return Aperture(f"{PREFIX.beamline_prefix}-AL-APTR-01:")


@devices.factory()
def beamstop() -> Beamstop:
    return Beamstop(f"{PREFIX.beamline_prefix}-MO-BS-01:")


@devices.factory()
def backlight() -> DualBacklight:
    return DualBacklight(prefix=PREFIX.beamline_prefix)


@devices.factory()
def detector_motion() -> YZStage:
    return YZStage(prefix=f"{PREFIX.beamline_prefix}-MO-DET-01:")


@devices.factory()
def dcm() -> DCM:
    return DCM(
        prefix=f"{PREFIX.beamline_prefix}-DI-DCM-01:",
        motion_prefix=f"{PREFIX.beamline_prefix}-MO-DCM-01:",
    )


@devices.factory()
def pmac() -> PMAC:
    return PMAC(PREFIX.beamline_prefix)


@devices.factory()
def oav(config_client) -> OAVBeamCentreFile:
    return OAVBeamCentreFile(
        prefix=f"{PREFIX.beamline_prefix}-DI-OAV-01:",
        config=OAVConfigBeamCentre(ZOOM_PARAMS_FILE, DISPLAY_CONFIG, config_client),
    )


@devices.factory()
def vgonio() -> VerticalGoniometer:
    return VerticalGoniometer(f"{PREFIX.beamline_prefix}-MO-VGON-01:")


@devices.factory()
def zebra() -> Zebra:
    return Zebra(
        prefix=f"{PREFIX.beamline_prefix}-EA-ZEBRA-01:",
        mapping=I24_ZEBRA_MAPPING,
    )


@devices.factory()
def shutter() -> InterlockedHutchShutter:
    return InterlockedHutchShutter(
        PREFIX.beamline_prefix, PSSInterlock(PREFIX.beamline_prefix)
    )


@devices.factory()
def focus_mirrors() -> FocusMirrorsMode:
    return FocusMirrorsMode(f"{PREFIX.beamline_prefix}-OP-MFM-01:")


@devices.factory()
def eiger_beam_center() -> DetectorBeamCenter:
    return DetectorBeamCenter(f"{PREFIX.beamline_prefix}-EA-EIGER-01:CAM:", "eiger_bc")


@devices.factory()
def jungfrau(
    path_provider: PathProvider,
) -> CommissioningJungfrauDetector:
    return CommissioningJungfrauDetector(
        f"{PREFIX.beamline_prefix}-EA-JFRAU-01:",
        f"{PREFIX.beamline_prefix}-JUNGFRAU-META:FD:",
        AutoMaxIncrementingPathProvider(path_provider),
        # The commissioning IOC serves its FastCS PVs at the root prefix, with no
        # CAM: sub-prefix as the Odin-backed jungfrau has.
        "",
    )


@devices.factory()
def synchrotron() -> Synchrotron:
    return Synchrotron()


@devices.factory()
def robot() -> BartRobot:
    return BartRobot(f"{PREFIX.beamline_prefix}-MO-ROBOT-01:")


@devices.factory()
def sample_shutter() -> MXZebraShutter:
    return MXZebraShutter(
        f"{PREFIX.beamline_prefix}-EA-SHTR-01:",
    )
