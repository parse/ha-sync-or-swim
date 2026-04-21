import eslint from "@eslint/js";
import tseslint from "typescript-eslint";
import eslintConfigPrettier from "eslint-config-prettier";
import globals from "globals";

export default tseslint.config(
  { ignores: ["dist/", "node_modules/"] },
  eslint.configs.recommended,
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  eslintConfigPrettier,
  {
    languageOptions: {
      globals: globals.node,
      parserOptions: {
        project: true,
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      eqeqeq: "error",
    },
  },
);
