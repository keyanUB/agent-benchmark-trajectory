class CreateCartItems < ActiveRecord::Migration[8.0]
  def change
    create_table :cart_items do |t|
      t.references :cart, null: false, foreign_key: true
      t.integer :item_id, null: false
      t.integer :count, null: false, default: 0
      t.timestamps
    end
    add_index :cart_items, [ :cart_id, :item_id ], unique: true
  end
end