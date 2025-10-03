"""
本模块定义了 yquoter 项目中所有自定义的异常类型。
"""

class YquoterError(Exception):
    """
    项目自定义的基础异常类。
    项目中所有其他的自定义异常都应继承自此类，
    这样用户可以只捕获这一个基础异常来处理所有已知的项目错误。
    """
    pass

class CodeFormatError(YquoterError, ValueError):
    """
    当股票代码的格式无法被识别或处理时抛出。
    继承自 ValueError 以保持部分语义兼容性。
    """
    pass

class DateFormatError(YquoterError, ValueError):
    """
    当日期字符串的格式无法被识别或处理时抛出。
    继承自 ValueError 以保持部分语义兼容性。
    """
    pass

class CacheError(YquoterError):
    """与缓存操作相关的基础异常。"""
    pass

class CacheSaveError(CacheError):
    """当保存缓存失败时抛出。"""
    pass

class CacheDirectoryError(CacheError):
    """当创建缓存目录失败时抛出。"""
    pass

class ConfigError(YquoterError):
    """当配置项缺失或格式错误时抛出。"""
    pass


class DataSourceError(YquoterError):
    """与数据源相关的错误，如数据源不存在或未初始化。"""
    pass

class ParameterError(YquoterError, ValueError):
    """当提供给API的参数无效时抛出。"""
    pass

class DataFetchError(YquoterError):
    """当从外部数据源获取数据失败时抛出。"""
    pass

class DataFormatError(YquoterError):
    """当获取到的数据格式不符合要求时抛出。"""
    pass

class IndicatorCalculationError(YquoterError):
    """在计算技术指标时发生错误。"""
    pass
# 将来可以根据需要在这里添加更多异常，例如：
# class DataNotFoundError(YquoterError):
#     """当请求的数据不存在时抛出。"""
#     pass