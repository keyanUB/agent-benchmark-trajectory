class CreateCarts < ActiveRecord::Migration[8.0]
  def change
    create_table :carts do |t|
      t.string :cart_id, null: false
      t.timestamps
    end
    add_index :carts, :cart_id, unique: true
  end
end