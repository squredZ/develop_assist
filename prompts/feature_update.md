你需要更新一个已有的 feature.yaml 来整合新的模块知识。

## 功能名
{{feature_name}}

## 当前 feature.yaml
```yaml
{{feature_yaml}}
```

## 新模块的 YAML
```yaml
{{module_name}}
```

## 指令

1. 在 modules 列表中追加新的模块索引。
2. 根据模块的 candidate_steps 可选追加新的 call_chain 步骤。
3. 根据模块的 failure_signals 可选追加新的 failure key logs。
4. 将 metadata.version 递增 1。
5. 更新 metadata.updated_at 为当前时间。
6. 如果 placement 或 matching 不确定，追加 review_notes。
7. 输出严格 JSON：

```json
{
  "updated_feature_yaml": "<更新后的 FeatureYaml YAML 字符串>",
  "change_summary": ["变更1"],
  "warnings": ["警告1"],
  "related_feature_suggestions": [
    {"feature": "other_feature", "reason": "原因"}
  ]
}
```

注意：
- 只能追加，不得删除或重写已有内容。
- 不得修改 name、display_name、description、keywords、metadata.owner、metadata.status。
