"""验证项目作为 uv 包安装后可导入核心命名空间。"""

from importlib import import_module
from importlib.metadata import distribution


def test_project_packages_are_importable() -> None:
    package = distribution("financial-document-risk-review")
    assert package.version == "0.1.0"
    assert any(
        str(path).endswith("_editable_impl_financial_document_risk_review.pth")
        for path in package.files or ()
    )

    for module_name in ("app", "engines", "evaluation"):
        assert import_module(module_name).__name__ == module_name
