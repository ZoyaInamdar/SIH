"""iceberg_wrapper -- adapter layer around OpenDrift's OpenBerg model.
 
Import IcebergDriftModel; nothing else in this package is part of the
public interface.
"""
 
from .iceberg_model import IcebergDriftModel, IcebergDriftModelError
 
__all__ = ["IcebergDriftModel", "IcebergDriftModelError"]
 