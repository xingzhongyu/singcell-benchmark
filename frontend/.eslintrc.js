module.exports = {
  extends: [
    'react-app',
    'react-app/jest'
  ],
  rules: {
    // 将所有错误降级为警告
    '@typescript-eslint/no-explicit-any': 'warn',
    '@typescript-eslint/no-unused-vars': 'warn',
    '@typescript-eslint/explicit-module-boundary-types': 'off',
    '@typescript-eslint/no-empty-function': 'warn',
    '@typescript-eslint/ban-ts-comment': 'warn',
    
    // React 相关规则降级为警告
    'react-hooks/exhaustive-deps': 'warn',
    'react-hooks/rules-of-hooks': 'warn',
    'react/jsx-no-target-blank': 'warn',
    'react/no-unescaped-entities': 'warn',
    
    // 一般规则降级为警告
    'no-unused-vars': 'warn',
    'no-console': 'warn',
    'no-debugger': 'warn',
    'no-empty': 'warn',
    'no-irregular-whitespace': 'warn',
    'no-unreachable': 'warn',
    'no-constant-condition': 'warn',
    
    // 关闭一些严格的格式检查
    'prefer-const': 'warn',
    'no-var': 'warn',
    'object-shorthand': 'warn',
    'prefer-arrow-callback': 'warn',
    
    // Import 相关规则降级为警告
    'import/first': 'warn',
    'import/order': 'warn',
    'import/no-unresolved': 'warn',
    'import/named': 'warn',
    
    // TypeScript 类型相关错误降级为警告
    '@typescript-eslint/ban-types': 'warn',
    '@typescript-eslint/no-inferrable-types': 'warn',
    '@typescript-eslint/no-non-null-assertion': 'warn',
    
    // JSX 相关
    'react/jsx-key': 'warn',
    'react/jsx-no-duplicate-props': 'warn',
    'react/jsx-no-undef': 'warn',
    'react/jsx-uses-react': 'warn',
    'react/jsx-uses-vars': 'warn',
    'react/no-danger': 'warn',
    'react/no-deprecated': 'warn',
    'react/no-direct-mutation-state': 'warn',
    'react/no-is-mounted': 'warn',
    'react/no-unknown-property': 'warn',
    'react/prop-types': 'off', // TypeScript 已经处理了类型检查
    'react/react-in-jsx-scope': 'off', // React 17+ 不需要导入 React
  },
  // 覆盖默认的错误级别
  overrides: [
    {
      files: ['**/*.ts', '**/*.tsx'],
      rules: {
        // TypeScript 文件中的规则
        '@typescript-eslint/no-explicit-any': 'warn',
        '@typescript-eslint/no-unused-vars': ['warn', { 
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_'
        }],
      }
    }
  ]
};

