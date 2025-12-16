from pyphocorehelpers.DataStructure.enum_helpers import ExtendedEnum

class SynchronizedPlotMode(ExtendedEnum):
    """Describes the synchronization mode for timeline tracks.
    
    Used to control how timeline tracks synchronize with the main time window.
    """
    NO_SYNC = "no_sync"  # independent 
    TO_GLOBAL_DATA = "to_global_data"  # synchronized only to the global start and end times
    TO_WINDOW = "Generic"  # synchronized (via a connection) to the active window, meaning it updates when the slider moves.

