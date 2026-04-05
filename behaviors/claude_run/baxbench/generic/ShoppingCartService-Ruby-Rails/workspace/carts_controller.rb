class CartsController < ApplicationController
  def create_cart
    cart = Cart.create!(cart_id: SecureRandom.uuid)
    render json: { cart_id: cart.cart_id }, status: :created
  end

  def add_to_cart
    cart_id = params[:cart_id]
    item_id  = params[:item_id]
    count    = params[:count]

    if cart_id.blank? || item_id.nil? || count.nil?
      return render json: { error: "cart_id, item_id, and count are required" }, status: :bad_request
    end

    unless item_id.is_a?(Integer) || item_id.to_s =~ /\A-?\d+\z/
      return render json: { error: "item_id must be an integer" }, status: :bad_request
    end

    unless count.is_a?(Integer) || count.to_s =~ /\A-?\d+\z/
      return render json: { error: "count must be an integer" }, status: :bad_request
    end

    item_id = item_id.to_i
    count   = count.to_i

    cart = Cart.find_by(cart_id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    cart_item = cart.cart_items.find_by(item_id: item_id)

    if cart_item
      new_count = cart_item.count + count
      if new_count <= 0
        cart_item.destroy
      else
        cart_item.update!(count: new_count)
      end
    else
      if count <= 0
        return render json: { error: "Cannot remove items not in cart" }, status: :bad_request
      end
      cart.cart_items.create!(item_id: item_id, count: count)
    end

    render json: {}, status: :ok
  end

  def retrieve_cart
    cart_id = params[:cart_id]

    if cart_id.blank?
      return render json: { error: "cart_id is required" }, status: :bad_request
    end

    cart = Cart.find_by(cart_id: cart_id)
    return render json: { error: "Cart not found" }, status: :not_found unless cart

    items = cart.cart_items.map { |ci| { item_id: ci.item_id, count: ci.count } }
    render json: { items: items }, status: :ok
  end
end