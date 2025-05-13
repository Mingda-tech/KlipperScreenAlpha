#!/bin/bash

# 设置基础目录
BASE_DIR="locales"

# 遍历所有语言目录
for lang_dir in "$BASE_DIR"/*/ ; do
    if [ -d "$lang_dir/LC_MESSAGES" ]; then
        po_file="$lang_dir/LC_MESSAGES/KlipperScreen.po"
        mo_file="$lang_dir/LC_MESSAGES/KlipperScreen.mo"
        
        if [ -f "$po_file" ]; then
            echo "Converting $po_file to $mo_file"
            msgfmt -o "$mo_file" "$po_file"
        else
            echo "Warning: $po_file not found"
        fi
    fi
done

echo "Conversion complete"